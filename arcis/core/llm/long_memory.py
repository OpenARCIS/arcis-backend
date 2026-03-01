import uuid
from datetime import datetime
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from fastembed import TextEmbedding

from arcis import Config
from arcis.logger import LOGGER

COLLECTION_NAME = "arcis_long_memory"
EMBEDDING_DIM_FASTEMBED = 384
EMBEDDING_DIM_GEMINI = 768

VALID_CATEGORIES = {"user_profile", "preference", "key_detail", "learned_fact"}


class LongTermMemory:

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
        self.client: Optional[QdrantClient] = None
        self._embed_fn = None
        self._embed_mode: str = "offline"  # "offline" or "online"
        self._embed_dim: int = EMBEDDING_DIM_FASTEMBED

    def init(self, mode: str = "offline"):
        """
        Connect to Qdrant and prepare the embedding function.

        Args:
            mode: "offline" for FastEmbed (CPU), "online" for Gemini Embedding API.
        """
        self._embed_mode = mode

        qdrant_url = Config.QDRANT_URL
        qdrant_key = Config.QDRANT_API_KEY

        self.client = QdrantClient(url=qdrant_url,api_key=qdrant_key,timeout=30)

        if mode == "online":
            self._setup_gemini_embedding()
        else:
            self._setup_fastembed()

        self._ensure_collection()
        LOGGER.info("LongTermMemory initialized")


    def _setup_fastembed(self):
        self._embed_fn = TextEmbedding("BAAI/bge-small-en-v1.5")
        self._embed_dim = EMBEDDING_DIM_FASTEMBED


    def _setup_gemini_embedding(self):
        from google import genai

        api_key = Config.GEMINI_API
        if not api_key:
            raise ValueError("GEMINI_API key required for online embedding mode")

        self._gemini_client = genai.Client(api_key=api_key)
        self._embed_dim = EMBEDDING_DIM_GEMINI


    def _ensure_collection(self):
        """Create collection if it doesn't already exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self._embed_dim,
                    distance=Distance.COSINE,
                ),
            )
            LOGGER.info(f"Created Qdrant collection: {COLLECTION_NAME}")


    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._embed_mode == "online":
            return self._embed_gemini(texts)
        return self._embed_fastembed(texts)


    def _embed_fastembed(self, texts: list[str]) -> list[list[float]]:
        embeddings = list(self._embed_fn.embed(texts))
        return [e.tolist() for e in embeddings]


    def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        result = self._gemini_client.models.embed_content(
            model="gemini-embedding-exp-03-07",
            contents=texts,
        )
        return [e.values for e in result.embeddings]


    def store(self, text: str, category: str = "key_detail", metadata: dict | None = None, source: str = "system") -> str:
        """
        Store a fact/memory into Qdrant.

        Returns the point ID (str).
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of: {VALID_CATEGORIES}")

        vector = self.embed([text])[0]
        point_id = str(uuid.uuid4())

        payload = {
            "text": text,
            "category": category,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {}),
        }

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        LOGGER.debug(f"Stored memory [{category}]: {text[:80]}...")
        return point_id


    def store_many(self, items: list[dict]) -> list[str]:
        """
        Bulk store multiple memories.

        Each item should have: text, category, and optionally metadata, source.
        Returns list of point IDs.
        """
        if not items:
            return []

        texts = [item["text"] for item in items]
        vectors = self.embed(texts)
        point_ids = []

        points = []
        for item, vector in zip(items, vectors):
            pid = str(uuid.uuid4())
            point_ids.append(pid)
            points.append(PointStruct(
                id=pid,
                vector=vector,
                payload={
                    "text": item["text"],
                    "category": item.get("category", "key_detail"),
                    "source": item.get("source", "system"),
                    "timestamp": datetime.now().isoformat(),
                    **(item.get("metadata") or {}),
                },
            ))

        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        LOGGER.debug(f"Stored {len(points)} memories in bulk")
        return point_ids


    def search(self, query: str, top_k: int = 3, category: str | None = None, score_threshold: float = 0.4) -> list[dict]:
        """
        Semantic search over long-term memory.

        Returns list of dicts with: text, category, score, source, timestamp.
        """
        vector = self.embed([query])[0]

        query_filter = None
        if category:
            query_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        return [
            {
                "text": hit.payload["text"],
                "category": hit.payload.get("category", ""),
                "score": hit.score,
                "source": hit.payload.get("source", ""),
                "timestamp": hit.payload.get("timestamp", ""),
            }
            for hit in results.points
        ]


    def get_user_profile(self) -> list[dict]:
        """Convenience: return all user_profile memories."""
        return self.search("user profile information", top_k=20, category="user_profile")


    def delete(self, point_id: str):
        """Delete a specific memory by its point ID."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[point_id],
        )
        LOGGER.debug(f"Deleted memory: {point_id}")


long_memory = LongTermMemory()
