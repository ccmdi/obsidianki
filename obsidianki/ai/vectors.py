"""Vector-based semantic deduplication for flashcards.

Simple JSON storage + API embeddings. No heavy dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

from obsidianki.cli.config import CONFIG_DIR, console

VECTORS_FILE = CONFIG_DIR / "vectors.json"

# Embedding endpoints
GEMINI_BATCH_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure Python cosine similarity."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore:
    """Simple vector store using JSON file + API embeddings."""

    def __init__(self):
        self._data: Optional[dict] = None
        self._embedder: Optional[BaseEmbedder] = None
        self._dims: Optional[int] = None

    @property
    def data(self) -> dict:
        """Lazy-load vector data from JSON file."""
        if self._data is None:
            if VECTORS_FILE.exists():
                try:
                    with open(VECTORS_FILE) as f:
                        loaded = json.load(f)
                    if not isinstance(loaded, dict):
                        loaded = {"_dims": self._get_expected_dims()}
                    # Check dimension compatibility
                    if loaded.get("_dims") and loaded["_dims"] != self._get_expected_dims():
                        console.print(f"[yellow]Embedder changed. Clearing vector index.[/yellow]")
                        loaded = {"_dims": self._get_expected_dims()}
                    self._data = loaded
                except (json.JSONDecodeError, KeyError):
                    self._data = {"_dims": self._get_expected_dims()}
            else:
                self._data = {"_dims": self._get_expected_dims()}
        return self._data

    def _save(self) -> None:
        """Save vector data to JSON file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(VECTORS_FILE, 'w') as f:
            json.dump(self._data, f)

    def _get_expected_dims(self) -> int:
        """Get expected embedding dimensions based on current embedder."""
        if os.environ.get("GEMINI_API_KEY"):
            return 768
        elif os.environ.get("OPENAI_API_KEY"):
            return 1536
        return 0  # Unknown

    @property
    def embedder(self) -> BaseEmbedder:
        """Get embedder - Gemini or OpenAI."""
        if self._embedder is None:
            if os.environ.get("GEMINI_API_KEY"):
                self._embedder = GeminiEmbedder()
            elif os.environ.get("OPENAI_API_KEY"):
                self._embedder = OpenAIEmbedder()
            else:
                raise ValueError(
                    "No API key for embeddings. Set GEMINI_API_KEY or OPENAI_API_KEY."
                )
        return self._embedder

    def add(self, fronts: List[str]) -> None:
        """Index flashcard fronts."""
        if not fronts:
            return

        fronts = [f for f in fronts if f.strip()]
        if not fronts:
            return

        console.print(f"[dim]Indexing {len(fronts)} card(s)...[/dim]")
        embeddings = self.embedder.embed(fronts)

        for front, embedding in zip(fronts, embeddings):
            card_id = self._hash(front)
            self.data[card_id] = {"text": front, "embedding": embedding}

        self.data["_dims"] = len(embeddings[0]) if embeddings else self._get_expected_dims()
        self._save()

    def find_similar(self, front: str, threshold: float, limit: int = 5) -> List[Tuple[str, float]]:
        """Find all similar existing cards above threshold.

        Returns:
            List of (similar_text, similarity_score) tuples, sorted by score descending
        """
        if self.count() == 0:
            return []

        front_id = self._hash(front)
        query_embedding = self.embedder.embed([front])[0]

        matches = []
        for card_id, card_data in self.data.items():
            if card_id.startswith("_"):  # Skip metadata
                continue
            if card_id == front_id:  # Skip self
                continue

            similarity = cosine_similarity(query_embedding, card_data["embedding"])
            if similarity >= threshold:
                matches.append((card_data["text"], similarity))

        # Sort by similarity descending, limit results
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]

    def find_similar_batch(
        self,
        fronts: List[str],
        threshold: float
    ) -> List[Tuple[int, str, List[Tuple[str, float]]]]:
        """Check multiple fronts for similarity.

        Returns:
            List of (index, front, [(similar_text, score), ...]) for cards with matches
        """
        results = []
        for i, front in enumerate(fronts):
            matches = self.find_similar(front, threshold)
            if matches:
                results.append((i, front, matches))
        return results

    def count(self) -> int:
        """Number of indexed cards."""
        return len([k for k in self.data.keys() if not k.startswith("_")])

    def clear(self) -> None:
        """Clear all indexed cards."""
        self._data = {"_dims": self._get_expected_dims()}
        self._save()

    def _hash(self, text: str) -> str:
        """Generate stable ID for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]


class BaseEmbedder:
    """Base class for embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class GeminiEmbedder(BaseEmbedder):
    """Embeddings via Gemini API (batched)."""

    def __init__(self, dimensions: int = 768):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")
        self.dimensions = dimensions
        self.model = "models/gemini-embedding-001"

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Gemini batch limit is 100, chunk if needed
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            embeddings = self._embed_batch(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        url = f"{GEMINI_BATCH_EMBED_URL}?key={self.api_key}"
        payload = {
            "requests": [
                {
                    "model": self.model,
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": self.dimensions
                }
                for text in texts
            ]
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return [item["values"] for item in data["embeddings"]]


class OpenAIEmbedder(BaseEmbedder):
    """Embeddings via OpenAI API."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found")
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        url = OPENAI_EMBED_URL
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": self.model, "input": texts}

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]


# Global lazy instance
_VECTORS: Optional[VectorStore] = None


def get_vectors() -> VectorStore:
    """Get or create the global vector store."""
    global _VECTORS
    if _VECTORS is None:
        _VECTORS = VectorStore()
    return _VECTORS
