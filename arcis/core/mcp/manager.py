import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Optional

from langchain_core.tools import StructuredTool

from arcis.core.mcp.client import connect_mcp_server, MCPConnection
from arcis.core.mcp.tool_registry import MCPToolRegistry
from arcis.models.mcp import MCPServerConfig
from arcis.logger import LOGGER


# Default threshold: below this number of tools, bind all to the LLM directly.
# Above this, use Qdrant semantic search to pre-filter.
DEFAULT_TOOL_THRESHOLD = 30


class MCPManager:
    """
    Singleton manager for MCP server connections and tool lifecycle.
    
    Usage:
        await mcp_manager.init()          # connects to all configured servers
        tools = mcp_manager.get_tools_for_task("send an email via gmail")
        await mcp_manager.shutdown()
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._stack: Optional[AsyncExitStack] = None
        self._connections: list[MCPConnection] = []
        self._registry = MCPToolRegistry()
        self._tool_threshold = DEFAULT_TOOL_THRESHOLD
        self._is_connected = False

    async def init(self,config_path: Optional[str] = None,tool_threshold: int = DEFAULT_TOOL_THRESHOLD):
        """
        Initialize MCP connections from a config file.
        
        Config file is a JSON file with structure:
        {
            "server_name": {
                "command": "npx",
                "args": ["-y", "@some/mcp-server"],
                "tool_timeout": 30
            },
            "another_server": {
                "url": "http://localhost:8080/mcp",
                "tool_timeout": 60
            }
        }
        """
        if self._is_connected:
            LOGGER.warning("MCPManager already initialized, skipping")
            return

        self._tool_threshold = tool_threshold

        # Load server configs
        servers = self._load_config(config_path)
        if not servers:
            LOGGER.info("MCP: No servers configured, MCP agent will have no tools")
            self._is_connected = True
            return

        # Initialize the tool registry (Qdrant collection)
        self._registry.init()

        # Connect to each server
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        for name, cfg in servers.items():
            try:
                connection = await connect_mcp_server(name, cfg, self._stack)
                self._connections.append(connection)
                self._registry.register_tools(connection.tools, server_name=name)
            except Exception as e:
                LOGGER.error(f"MCP server '{name}': failed to connect: {e}")

        total = self._registry.tool_count
        LOGGER.info(f"MCP: {len(self._connections)} servers connected, {total} total tools")
        self._is_connected = True

    def _load_config(self, config_path: Optional[str]) -> dict[str, MCPServerConfig]:
        """Load MCP server configurations from a JSON file."""

        if not config_path:
            LOGGER.info("MCP: No config path set (MCP_SERVERS_CONFIG_PATH)")
            return {}

        path = Path(config_path)
        if not path.exists():
            LOGGER.warning(f"MCP config file not found: {config_path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            LOGGER.error(f"MCP: Failed to read config file: {e}")
            return {}

        servers = {}
        for name, cfg_dict in raw.items():
            try:
                servers[name] = MCPServerConfig(**cfg_dict)
            except Exception as e:
                LOGGER.error(f"MCP: Invalid config for server '{name}': {e}")

        return servers

    def get_tools_for_task(self, task_description: str) -> list[StructuredTool]:
        """
        Get MCP tools relevant to a task.
        
        Hybrid approach:
        - If total tools < threshold: returns ALL tools (let the LLM pick)
        - If total tools >= threshold: uses Qdrant semantic search to pre-filter
        """
        total = self._registry.tool_count
        if total == 0:
            return []

        if total < self._tool_threshold:
            LOGGER.debug(f"MCP: {total} tools < threshold {self._tool_threshold}, returning all")
            return self._registry.get_all_tools()

        LOGGER.debug(f"MCP: {total} tools >= threshold, using semantic search for: {task_description[:80]}")
        return self._registry.search_tools(task_description, top_k=15)

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def total_tools(self) -> int:
        return self._registry.tool_count

    async def shutdown(self):
        """Close all MCP connections."""
        if self._stack:
            try:
                await self._stack.aclose()
            except Exception as e:
                LOGGER.warning(f"MCP: Error during shutdown: {e}")
        self._connections.clear()
        self._registry.clear()
        self._is_connected = False
        LOGGER.info("MCP: All connections closed")


mcp_manager = MCPManager()
