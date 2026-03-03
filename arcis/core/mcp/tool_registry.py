"""MCP Tool Registry: stores MCP tool metadata in Qdrant for semantic search."""

import uuid
from typing import Optional

from langchain_core.tools import StructuredTool
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)

from arcis.core.llm.long_memory import long_memory
from arcis.logger import LOGGER

COLLECTION_NAME = "arcis_mcp_tools"


class MCPToolRegistry:
    """
    Registry that stores MCP tool metadata in Qdrant for semantic search.
    
    Maintains a mapping from tool_name -> StructuredTool for quick lookup,
    and stores embeddings of tool descriptions in Qdrant for semantic matching.
    """

    def __init__(self):
        self._tools: dict[str, StructuredTool] = {}  # tool_name -> StructuredTool
        self._initialized = False

    def init(self):
        """Initialize the Qdrant collection for MCP tools."""
        if self._initialized:
            return

        if not long_memory.client:
            LOGGER.warning("MCPToolRegistry: Qdrant not available, semantic search disabled")
            self._initialized = True
            return

        # Create collection if needed
        collections = [c.name for c in long_memory.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            long_memory.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=long_memory._embed_dim,
                    distance=Distance.COSINE,
                ),
            )
            LOGGER.info(f"Created Qdrant collection: {COLLECTION_NAME}")
        
        self._initialized = True

    def register_tools(self, tools: list[StructuredTool], server_name: str):
        """
        Register MCP tools in the in-memory map and in Qdrant for semantic search.
        """
        if not tools:
            return

        # Store in memory map
        for tool in tools:
            self._tools[tool.name] = tool

        # Store in Qdrant if available
        if not long_memory.client:
            LOGGER.debug("Skipping Qdrant storage (not available)")
            return

        texts = [f"{tool.name}: {tool.description}" for tool in tools]
        vectors = long_memory.embed(texts)

        points = []
        for tool, vector in zip(tools, vectors):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "tool_name": tool.name,
                    "description": tool.description,
                    "server_name": server_name,
                },
            ))

        long_memory.client.upsert(collection_name=COLLECTION_NAME, points=points)
        LOGGER.debug(f"Stored {len(points)} MCP tool embeddings in Qdrant")

    def search_tools(
        self, task_description: str, top_k: int = 10, score_threshold: float = 0.3
    ) -> list[StructuredTool]:
        """
        Semantic search for MCP tools relevant to a task description.
        
        Returns a list of StructuredTools ranked by relevance.
        """
        if not long_memory.client:
            LOGGER.debug("Qdrant not available, returning all tools")
            return list(self._tools.values())

        vector = long_memory.embed([task_description])[0]

        results = long_memory.client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=top_k,
            score_threshold=score_threshold,
        )

        matched_tools = []
        for hit in results.points:
            tool_name = hit.payload.get("tool_name")
            if tool_name and tool_name in self._tools:
                matched_tools.append(self._tools[tool_name])
                LOGGER.debug(f"Matched MCP tool '{tool_name}' (score: {hit.score:.3f})")

        return matched_tools

    def get_all_tools(self) -> list[StructuredTool]:
        """Return all registered MCP tools."""
        return list(self._tools.values())

    @property
    def tool_count(self) -> int:
        """Total number of registered MCP tools."""
        return len(self._tools)

    def clear(self):
        """Clear all tools and Qdrant data."""
        self._tools.clear()
        if long_memory.client:
            try:
                long_memory.client.delete_collection(COLLECTION_NAME)
                LOGGER.info(f"Deleted Qdrant collection: {COLLECTION_NAME}")
            except Exception:
                pass
        self._initialized = False
