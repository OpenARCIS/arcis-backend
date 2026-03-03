from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    command: Optional[str] = Field(default=None, description="Command for stdio-based MCP servers")
    args: List[str] = Field(default_factory=list, description="Arguments for the command")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables for the server process")
    url: Optional[str] = Field(default=None, description="URL for HTTP-based MCP servers (streamable HTTP)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers for HTTP-based servers")
    tool_timeout: int = Field(default=30, description="Timeout in seconds for individual tool calls")
