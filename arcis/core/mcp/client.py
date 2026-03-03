import asyncio
from contextlib import AsyncExitStack
from typing import Any, Optional

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

from arcis.models.mcp import MCPServerConfig
from arcis.logger import LOGGER


def _json_schema_to_pydantic(name: str, schema: dict) -> type[BaseModel]:
    """
    Convert a JSON Schema (from MCP tool inputSchema) to a Pydantic model
    so LangChain can build the tool's args_schema.
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    field_definitions = {}
    for field_name, field_schema in properties.items():
        field_type = _json_type_to_python(field_schema)
        if field_name in required:
            field_definitions[field_name] = (field_type, ...)
        else:
            field_definitions[field_name] = (Optional[field_type], None)

    model = create_model(name, **field_definitions)
    return model


def _json_type_to_python(schema: dict) -> type:
    """Map JSON Schema types to Python types."""
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    json_type = schema.get("type", "string")
    return type_map.get(json_type, str)


class MCPConnection:
    """Holds an active MCP server connection and its wrapped tools."""

    def __init__(self, name: str, session, tools: list[StructuredTool]):
        self.name = name
        self.session = session
        self.tools = tools


async def connect_mcp_server(name: str,cfg: MCPServerConfig,stack: AsyncExitStack) -> MCPConnection:
    """
    Connect to a single MCP server and return the connection with wrapped tools.
    
    Supports both stdio (command-based) and HTTP (streamable HTTP) transports.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    session: ClientSession

    if cfg.command:
        params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env=cfg.env or None,
        )
        read, write = await stack.enter_async_context(stdio_client(params))

    elif cfg.url:
        from mcp.client.streamable_http import streamable_http_client

        http_client = await stack.enter_async_context(
            httpx.AsyncClient(
                headers=cfg.headers or None,
                follow_redirects=True,
                timeout=None,
            )
        )
        read, write, _ = await stack.enter_async_context(
            streamable_http_client(cfg.url, http_client=http_client)
        )
    else:
        raise ValueError(f"MCP server '{name}': no command or url configured")

    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()

    # List all tools from the server and wrap them
    tools_result = await session.list_tools()
    wrapped_tools: list[StructuredTool] = []

    for tool_def in tools_result.tools:
        wrapper = _create_langchain_tool(session, name, tool_def, cfg.tool_timeout)
        wrapped_tools.append(wrapper)
        LOGGER.debug(f"MCP: wrapped tool '{wrapper.name}' from server '{name}'")

    LOGGER.info(f"MCP server '{name}': connected, {len(wrapped_tools)} tools registered")
    return MCPConnection(name=name, session=session, tools=wrapped_tools)


def _create_langchain_tool(session, server_name: str, tool_def, tool_timeout: int) -> StructuredTool:
    """Wrap a single MCP tool definition as a LangChain StructuredTool."""
    from mcp import types as mcp_types

    tool_name = f"mcp_{server_name}_{tool_def.name}"
    description = tool_def.description or tool_def.name
    input_schema = tool_def.inputSchema or {"type": "object", "properties": {}}

    # Build a Pydantic model for the args schema
    args_model = _json_schema_to_pydantic(f"{tool_name}_args", input_schema)

    # Keep references in closure
    original_name = tool_def.name

    async def _arun(**kwargs: Any) -> str:
        """Execute the MCP tool call."""
        try:
            result = await asyncio.wait_for(
                session.call_tool(original_name, arguments=kwargs),
                timeout=tool_timeout,
            )
        except asyncio.TimeoutError:
            LOGGER.warning(f"MCP tool '{tool_name}' timed out after {tool_timeout}s")
            return f"(MCP tool call timed out after {tool_timeout}s)"

        parts = []
        for block in result.content:
            if isinstance(block, mcp_types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"

    return StructuredTool(
        name=tool_name,
        description=description,
        args_schema=args_model,
        coroutine=_arun,
        return_direct=False,
    )
