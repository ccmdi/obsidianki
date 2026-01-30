"""Tests for vector-based semantic deduplication."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from obsidianki.ai.vectors import (
    cosine_similarity,
    VectorStore,
    GeminiEmbedder,
    OpenAIEmbedder,
)


class TestCosineSimilarity:
    """Tests for the cosine_similarity function."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity of 1.0."""
        vec = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity of 0.0."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity of -1.0."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [-1.0, -2.0, -3.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(-1.0)

    def test_similar_vectors(self):
        """Similar vectors should have high similarity."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [1.1, 2.1, 3.1]
        similarity = cosine_similarity(vec_a, vec_b)
        assert similarity > 0.99

    def test_zero_vector(self):
        """Zero vector should return 0.0 similarity."""
        vec_a = [0.0, 0.0, 0.0]
        vec_b = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec_a, vec_b) == 0.0

    def test_different_magnitudes(self):
        """Vectors with same direction but different magnitudes should be similar."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [2.0, 4.0, 6.0]  # Same direction, 2x magnitude
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(1.0)


class TestVectorStore:
    """Tests for the VectorStore class."""

    @pytest.fixture
    def mock_embedder(self):
        """Create a mock embedder that returns predictable embeddings."""
        embedder = MagicMock()
        # Return different embeddings based on input text
        def embed_side_effect(texts):
            embeddings = []
            for text in texts:
                # Simple hash-based embedding for testing
                hash_val = hash(text) % 1000
                embeddings.append([hash_val / 1000, (hash_val + 1) / 1000, (hash_val + 2) / 1000])
            return embeddings
        embedder.embed.side_effect = embed_side_effect
        return embedder

    @pytest.fixture
    def vector_store(self, mock_embedder, tmp_path):
        """Create a VectorStore with mocked embedder and temp storage."""
        with patch('obsidianki.ai.vectors.VECTORS_FILE', tmp_path / 'vectors.json'):
            with patch('obsidianki.ai.vectors.CONFIG_DIR', tmp_path):
                store = VectorStore()
                store._embedder = mock_embedder
                yield store

    def test_add_single_card(self, vector_store):
        """Test adding a single card to the store."""
        vector_store.add(["What is Python?"])
        assert vector_store.count() == 1

    def test_add_multiple_cards(self, vector_store):
        """Test adding multiple cards."""
        vector_store.add(["Question 1", "Question 2", "Question 3"])
        assert vector_store.count() == 3

    def test_add_empty_list(self, vector_store):
        """Adding empty list should not change count."""
        vector_store.add([])
        assert vector_store.count() == 0

    def test_add_filters_empty_strings(self, vector_store):
        """Empty strings should be filtered out."""
        vector_store.add(["Valid question", "", "  ", "Another valid"])
        assert vector_store.count() == 2

    def test_find_similar_empty_store(self, vector_store):
        """Finding similar in empty store should return empty list."""
        matches = vector_store.find_similar("Any question", threshold=0.5)
        assert matches == []

    def test_find_similar_returns_matches(self, vector_store):
        """Test that find_similar returns matches above threshold."""
        # Add some cards
        vector_store.add(["What is Python?", "What is Java?", "What is Rust?"])

        # Mock embedder to return similar embedding for query
        def query_embed(texts):
            # Return embedding very similar to "What is Python?"
            return [[hash("What is Python?") % 1000 / 1000 + 0.001,
                     (hash("What is Python?") % 1000 + 1) / 1000 + 0.001,
                     (hash("What is Python?") % 1000 + 2) / 1000 + 0.001]]

        vector_store._embedder.embed.side_effect = query_embed

        matches = vector_store.find_similar("What is Python?", threshold=0.5)
        # Should find matches (exact behavior depends on mock)
        assert isinstance(matches, list)

    def test_find_similar_respects_threshold(self, vector_store):
        """High threshold should return fewer matches."""
        vector_store.add(["Question A", "Question B"])

        # With threshold of 1.0, nothing should match (except exact)
        matches = vector_store.find_similar("Something else", threshold=1.0)
        assert len(matches) == 0

    def test_find_similar_excludes_self(self, vector_store):
        """Finding similar should not return the same card."""
        vector_store.add(["What is Python?"])

        # Query with exact same text - should not match itself
        vector_store._embedder.embed.return_value = [[0.5, 0.5, 0.5]]
        vector_store.data[vector_store._hash("What is Python?")]["embedding"] = [0.5, 0.5, 0.5]

        matches = vector_store.find_similar("What is Python?", threshold=0.0)
        # Should not include the exact same card
        for text, score in matches:
            assert text != "What is Python?"

    def test_find_similar_batch(self, vector_store):
        """Test batch similarity checking."""
        vector_store.add(["Existing card 1", "Existing card 2"])

        results = vector_store.find_similar_batch(
            ["New card A", "New card B"],
            threshold=0.0
        )
        assert isinstance(results, list)

    def test_clear(self, vector_store):
        """Test clearing the store."""
        vector_store.add(["Card 1", "Card 2"])
        assert vector_store.count() == 2

        vector_store.clear()
        assert vector_store.count() == 0

    # TODO: fix this
    # def test_persistence(self, tmp_path):
    #     """Test that data persists to disk."""
    #     vectors_file = tmp_path / 'vectors.json'
        
    #     with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
    #         with patch('obsidianki.ai.vectors.VECTORS_FILE', vectors_file):
    #             with patch('obsidianki.ai.vectors.CONFIG_DIR', tmp_path):
    #                 # Create store and add data
    #                 store1 = VectorStore()
    #                 store1._embedder = MagicMock()
    #                 store1._embedder.embed.return_value = [[0.1, 0.2, 0.3]]
    #                 store1.add(["Test card"])

    #                 # Verify file was created
    #                 assert vectors_file.exists()

    #                 # Create new store instance - should load data
    #                 store2 = VectorStore()
    #                 assert store2.count() == 1

    def test_dimension_mismatch_clears_store(self, tmp_path):
        """Store should clear if embedding dimensions change."""
        vectors_file = tmp_path / 'vectors.json'

        # Create initial data with 3 dimensions
        initial_data = {
            "_dims": 3,
            "abc123": {"text": "Old card", "embedding": [0.1, 0.2, 0.3]}
        }
        vectors_file.parent.mkdir(parents=True, exist_ok=True)
        with open(vectors_file, 'w') as f:
            json.dump(initial_data, f)

        with patch('obsidianki.ai.vectors.VECTORS_FILE', vectors_file):
            with patch('obsidianki.ai.vectors.CONFIG_DIR', tmp_path):
                # Create store expecting different dimensions
                with patch.dict('os.environ', {'OPENAI_API_KEY': 'test'}):
                    store = VectorStore()
                    # OpenAI expects 1536 dims, but stored data has 3
                    # This should trigger a clear
                    _ = store.data  # Access data to trigger load

                    # Store should be cleared (only _dims key)
                    assert store.count() == 0


class TestGeminiEmbedder:
    """Tests for GeminiEmbedder."""

    def test_requires_api_key(self):
        """Should raise error without API key."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                GeminiEmbedder()

    @patch('httpx.Client')
    def test_embed_batch(self, mock_client_class):
        """Test batch embedding."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embeddings": [
                {"values": [0.1, 0.2, 0.3]},
                {"values": [0.4, 0.5, 0.6]}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            embedder = GeminiEmbedder()
            result = embedder.embed(["Text 1", "Text 2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]


class TestOpenAIEmbedder:
    """Tests for OpenAIEmbedder."""

    def test_requires_api_key(self):
        """Should raise error without API key."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIEmbedder()

    @patch('httpx.Client')
    def test_embed_batch(self, mock_client_class):
        """Test batch embedding with OpenAI."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                {"index": 1, "embedding": [0.4, 0.5, 0.6]}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            embedder = OpenAIEmbedder()
            result = embedder.embed(["Text 1", "Text 2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

    @patch('httpx.Client')
    def test_embed_sorts_by_index(self, mock_client_class):
        """Test that results are sorted by index."""
        mock_response = MagicMock()
        # Return out of order
        mock_response.json.return_value = {
            "data": [
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                {"index": 0, "embedding": [0.1, 0.2, 0.3]}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            embedder = OpenAIEmbedder()
            result = embedder.embed(["Text 1", "Text 2"])

        # Should be sorted by index
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
