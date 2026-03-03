from typing import Optional, Dict, List, Literal
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    transport: Optional[Literal["stdio", "streamable_http", "sse"]] = Field(
        default=None,
        description="Transport protocol. Auto-detected if not set: 'stdio' when command is set, 'streamable_http' when url is set. Set explicitly to 'sse' for SSE-based servers."
    )
    command: Optional[str] = Field(default=None, description="Command for stdio-based MCP servers")
    args: List[str] = Field(default_factory=list, description="Arguments for the command")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables for the server process")
    url: Optional[str] = Field(default=None, description="URL for HTTP/SSE-based MCP servers")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers for HTTP/SSE-based servers")
    tool_timeout: int = Field(default=30, description="Timeout in seconds for individual tool calls")

