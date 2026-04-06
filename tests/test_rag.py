"""
tests/test_rag.py — Tests for the RAG pipeline (chunking, embedding, retrieval).
"""
import pytest
from unittest.mock import patch, MagicMock


class TestChunking:
    """Tests for the semantic chunking function."""

    def test_empty_string_returns_empty(self):
        from app.rag.pipeline import chunk_text
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty(self):
        from app.rag.pipeline import chunk_text
        assert chunk_text("   \n\n   ") == []

    def test_single_short_paragraph_returns_one_chunk(self):
        from app.rag.pipeline import chunk_text
        text = "This is a short paragraph."
        chunks = chunk_text(text, max_tokens=100, overlap=0)
        assert len(chunks) == 1
        assert "short paragraph" in chunks[0]

    def test_multiple_paragraphs_split_correctly(self):
        from app.rag.pipeline import chunk_text
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_text(text, max_tokens=5, overlap=0)
        assert len(chunks) >= 2

    def test_overlap_adds_context_to_subsequent_chunks(self):
        from app.rag.pipeline import chunk_text
        # Build text long enough to force chunking
        para_a = " ".join([f"wordA{i}" for i in range(60)])
        para_b = " ".join([f"wordB{i}" for i in range(60)])
        text = para_a + "\n\n" + para_b
        chunks = chunk_text(text, max_tokens=80, overlap=10)
        # Second chunk should contain tail words from first
        if len(chunks) > 1:
            last_words_first = para_a.split()[-10:]
            overlap_found = any(w in chunks[1] for w in last_words_first)
            assert overlap_found

    def test_long_single_paragraph_is_split_by_sentence(self):
        from app.rag.pipeline import chunk_text
        sentences = [f"This is sentence number {i} about AI and ML." for i in range(20)]
        text = " ".join(sentences)
        chunks = chunk_text(text, max_tokens=50, overlap=0)
        assert len(chunks) > 1

    def test_chunks_are_strings(self):
        from app.rag.pipeline import chunk_text
        text = "Hello world.\n\nSecond paragraph here."
        chunks = chunk_text(text)
        assert all(isinstance(c, str) for c in chunks)

    def test_chunks_non_empty(self):
        from app.rag.pipeline import chunk_text
        text = "Some content here.\n\nMore content here."
        chunks = chunk_text(text)
        assert all(len(c.strip()) > 0 for c in chunks)

    def test_no_overlap_zero(self):
        from app.rag.pipeline import chunk_text
        para_a = " ".join([f"wordA{i}" for i in range(60)])
        para_b = " ".join([f"wordB{i}" for i in range(60)])
        text = para_a + "\n\n" + para_b
        chunks = chunk_text(text, max_tokens=70, overlap=0)
        if len(chunks) > 1:
            # Without overlap, second chunk should NOT contain words from first
            last_word_first = para_a.split()[-1]
            assert last_word_first not in chunks[1]

    def test_max_tokens_respected_approximately(self):
        from app.rag.pipeline import chunk_text
        text = "\n\n".join([" ".join([f"w{j}" for j in range(30)]) for i in range(10)])
        chunks = chunk_text(text, max_tokens=50, overlap=0)
        for chunk in chunks:
            # Allow some flexibility for overlap and sentence boundaries
            assert len(chunk.split()) <= 80


class TestEmbedder:
    def test_get_embedder_returns_model(self):
        from app.rag.pipeline import get_embedder
        # Reset singleton for test
        import app.rag.pipeline as rag
        rag._embedder = None
        embedder = get_embedder()
        assert embedder is not None

    def test_embedder_is_singleton(self):
        from app.rag.pipeline import get_embedder
        e1 = get_embedder()
        e2 = get_embedder()
        assert e1 is e2

    def test_embedder_produces_vectors(self):
        from app.rag.pipeline import get_embedder
        embedder = get_embedder()
        vecs = embedder.encode(["Hello world"], convert_to_list=True)
        assert len(vecs) == 1
        assert len(vecs[0]) > 0
        assert all(isinstance(v, float) for v in vecs[0])

    def test_embedding_dimension_consistent(self):
        from app.rag.pipeline import get_embedder
        embedder = get_embedder()
        v1 = embedder.encode(["Short text"], convert_to_list=True)[0]
        v2 = embedder.encode(["Much longer text about AI and machine learning systems"], convert_to_list=True)[0]
        assert len(v1) == len(v2)


class TestStoreAndRetrieve:
    @patch("app.rag.pipeline.get_chroma")
    @patch("app.rag.pipeline.get_embedder")
    def test_store_context_calls_upsert(self, mock_embedder_fn, mock_chroma_fn):
        from app.rag.pipeline import store_context

        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]
        mock_embedder_fn.return_value = mock_embedder

        mock_collection = MagicMock()
        mock_chroma = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection
        mock_chroma_fn.return_value = mock_chroma

        store_context(
            collection_name="test_collection",
            doc_id="doc_001",
            text="Some content to store in the vector database.",
            metadata={"user_id": "user_1", "type": "profile"},
        )

        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args[1]
        assert "ids" in call_kwargs
        assert "documents" in call_kwargs
        assert "embeddings" in call_kwargs

    @patch("app.rag.pipeline.get_chroma")
    @patch("app.rag.pipeline.get_embedder")
    def test_store_empty_text_skips_upsert(self, mock_embedder_fn, mock_chroma_fn):
        from app.rag.pipeline import store_context

        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection
        mock_chroma_fn.return_value = mock_chroma

        store_context("test", "doc_empty", "", {"user_id": "u1"})
        mock_collection.upsert.assert_not_called()

    @patch("app.rag.pipeline.get_chroma")
    @patch("app.rag.pipeline.get_embedder")
    def test_retrieve_context_returns_list(self, mock_embedder_fn, mock_chroma_fn):
        from app.rag.pipeline import retrieve_context

        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]
        mock_embedder_fn.return_value = mock_embedder

        mock_collection = MagicMock()
        mock_collection.query.return_value = {"documents": [["chunk 1", "chunk 2"]]}
        mock_chroma = MagicMock()
        mock_chroma.get_collection.return_value = mock_collection
        mock_chroma_fn.return_value = mock_chroma

        results = retrieve_context("test_collection", "AI and RAG systems", n_results=2)
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0] == "chunk 1"

    @patch("app.rag.pipeline.get_chroma")
    def test_retrieve_missing_collection_returns_empty(self, mock_chroma_fn):
        from app.rag.pipeline import retrieve_context

        mock_chroma = MagicMock()
        mock_chroma.get_collection.side_effect = Exception("Collection not found")
        mock_chroma_fn.return_value = mock_chroma

        results = retrieve_context("nonexistent_collection", "query")
        assert results == []

    @patch("app.rag.pipeline.get_chroma")
    @patch("app.rag.pipeline.get_embedder")
    def test_retrieve_with_where_filter(self, mock_embedder_fn, mock_chroma_fn):
        from app.rag.pipeline import retrieve_context

        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]
        mock_embedder_fn.return_value = mock_embedder

        mock_collection = MagicMock()
        mock_collection.query.return_value = {"documents": [["filtered chunk"]]}
        mock_chroma = MagicMock()
        mock_chroma.get_collection.return_value = mock_collection
        mock_chroma_fn.return_value = mock_chroma

        results = retrieve_context(
            "profile_reports",
            "writing style",
            where={"user_id": "user_123"},
        )
        call_kwargs = mock_collection.query.call_args[1]
        assert "where" in call_kwargs
        assert call_kwargs["where"] == {"user_id": "user_123"}
        assert results == ["filtered chunk"]

    @patch("app.rag.pipeline.get_chroma")
    @patch("app.rag.pipeline.get_embedder")
    def test_retrieve_query_failure_returns_empty(self, mock_embedder_fn, mock_chroma_fn):
        from app.rag.pipeline import retrieve_context

        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]
        mock_embedder_fn.return_value = mock_embedder

        mock_collection = MagicMock()
        mock_collection.query.side_effect = Exception("Query failed")
        mock_chroma = MagicMock()
        mock_chroma.get_collection.return_value = mock_collection
        mock_chroma_fn.return_value = mock_chroma

        results = retrieve_context("test", "query")
        assert results == []

    @patch("app.rag.pipeline.get_chroma")
    @patch("app.rag.pipeline.get_embedder")
    def test_store_metadata_flattened(self, mock_embedder_fn, mock_chroma_fn):
        """ChromaDB only accepts str metadata values — verify flattening."""
        from app.rag.pipeline import store_context

        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]
        mock_embedder_fn.return_value = mock_embedder

        mock_collection = MagicMock()
        mock_chroma = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection
        mock_chroma_fn.return_value = mock_chroma

        store_context(
            "test",
            "doc_meta",
            "Some content about metadata handling.",
            metadata={"user_id": "u1", "count": 42, "flag": True},
        )

        call_kwargs = mock_collection.upsert.call_args[1]
        for meta in call_kwargs["metadatas"]:
            assert all(isinstance(v, str) for v in meta.values())
