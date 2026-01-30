"""Vector-based semantic deduplication for flashcards.

Uses ChromaDB for storage and sentence-transformers for local embeddings.
Provides a feedback loop where the LLM can revise cards based on similarity.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection
    from chromadb import ClientAPI

from obsidianki.cli.config import CONFIG_DIR, console

VECTORS_DIR = CONFIG_DIR / "vectors"


class VectorStore:
    """Lazy-loaded vector store for flashcard semantic deduplication."""

    def __init__(self):
        self._client: Optional[ClientAPI] = None
        self._collection: Optional[Collection] = None
        self._model: Optional[BaseEmbedder] = None

    @property
    def collection(self) -> Collection:
        """Lazy-load ChromaDB collection."""
        if self._collection is None:
            try:
                import chromadb
            except ImportError:
                raise ImportError(
                    "ChromaDB is required for vector deduplication. "
                    "Install with: pip install chromadb"
                )

            VECTORS_DIR.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(VECTORS_DIR))
            self._collection = self._client.get_or_create_collection(
                name="flashcards",
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    @property
    def model(self) -> BaseEmbedder:
        """Lazy-load embedding model."""
        if self._model is None:
            self._model = LocalEmbedder()
        return self._model

    def add(self, fronts: List[str]) -> None:
        """Index flashcard fronts."""
        if not fronts:
            return

        # Filter out empty strings and duplicates
        fronts = [f for f in fronts if f.strip()]
        if not fronts:
            return

        console.print(f"[dim]Indexing {len(fronts)} card(s) in vector store...[/dim]")
        embeddings = self.model.embed(fronts)
        ids = [self._hash(f) for f in fronts]

        # Upsert to handle duplicates
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=fronts
        )
        console.print(f"[dim]Vector index now has {self.count()} cards[/dim]")

    def find_similar(self, front: str, threshold: float) -> Optional[Tuple[str, float]]:
        """Find most similar existing card above threshold.

        Args:
            front: The flashcard front text to check
            threshold: Minimum cosine similarity (0-1) to consider a match

        Returns:
            Tuple of (similar_front, similarity_score) or None if no match
        """
        if self.collection.count() == 0:
            return None

        # Don't match against itself
        front_id = self._hash(front)

        results = self.collection.query(
            query_embeddings=[self.model.embed([front])[0]],
            n_results=2,  # Get 2 in case first is itself
            include=["documents", "distances"]
        )

        if not results["documents"] or not results["documents"][0]:
            return None

        # Find best match that isn't the same card
        for i, doc in enumerate(results["documents"][0]):
            doc_id = self._hash(doc)
            if doc_id == front_id:
                continue

            # ChromaDB returns cosine distance, convert to similarity
            distance = results["distances"][0][i]
            similarity = 1 - distance

            if similarity >= threshold:
                return (doc, similarity)

        return None

    def find_similar_batch(
        self,
        fronts: List[str],
        threshold: float
    ) -> List[Tuple[int, str, str, float]]:
        """Check multiple fronts for similarity.

        Args:
            fronts: List of flashcard front texts to check
            threshold: Minimum cosine similarity to flag

        Returns:
            List of (index, front, similar_existing, similarity) for matches only
        """
        matches = []
        for i, front in enumerate(fronts):
            similar = self.find_similar(front, threshold)
            if similar:
                existing, score = similar
                matches.append((i, front, existing, score))
        return matches

    def count(self) -> int:
        """Number of indexed cards."""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all indexed cards."""
        if self._client is not None:
            self._client.delete_collection("flashcards")
            self._collection = None

    def _hash(self, text: str) -> str:
        """Generate stable ID for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]


class BaseEmbedder:
    """Base class for embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class LocalEmbedder(BaseEmbedder):
    """Local embeddings using sentence-transformers."""

    def __init__(self):
        self._model = None
        self._loaded = False

    def _get_device(self) -> str:
        """Detect best available device (cuda > mps > cpu)."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    @property
    def model(self):
        if self._model is None:
            try:
                # Suppress noisy logging from transformers/torch
                import logging
                import warnings
                logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
                logging.getLogger("transformers").setLevel(logging.WARNING)
                warnings.filterwarnings("ignore", message=".*position_ids.*")

                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for vector deduplication. "
                    "Install with: pip install sentence-transformers"
                )
            device = self._get_device()
            if not self._loaded:
                console.print(f"[dim]Loading embedding model ({device})...[/dim]")
            self._model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
            self._loaded = True
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, show_progress_bar=False).tolist()


# Global lazy instance
_VECTORS: Optional[VectorStore] = None


def get_vectors() -> VectorStore:
    """Get or create the global vector store."""
    global _VECTORS
    if _VECTORS is None:
        _VECTORS = VectorStore()
    return _VECTORS
