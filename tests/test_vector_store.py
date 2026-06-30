"""
Tests for the vector store sparse index caching logic.

The Phase 4 fix added a module-level TTL cache to avoid rebuilding the TF-IDF
index on every sparse/hybrid query. These tests verify that caching works.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch


class TestSparseIndexCaching:
    def _reset_module_state(self):
        """Reset the module-level cache so tests are independent."""
        import vectraiq.ai.vector_store as vs
        vs._sparse_index = None
        vs._sparse_index_built_at = 0.0

    def test_sparse_index_built_on_first_call(self):
        self._reset_module_state()
        import vectraiq.ai.vector_store as vs

        mock_index = MagicMock()
        with patch.object(vs, "_build_sparse_index", return_value=mock_index) as build_fn:
            result = vs._get_sparse_index()

        build_fn.assert_called_once()
        assert result is mock_index

    def test_sparse_index_reused_within_ttl(self):
        self._reset_module_state()
        import time
        import vectraiq.ai.vector_store as vs

        mock_index = MagicMock()
        with patch.object(vs, "_build_sparse_index", return_value=mock_index) as build_fn:
            # First call — builds
            vs._get_sparse_index()
            # Second call within TTL — reuses
            vs._get_sparse_index()
            # Third call within TTL — reuses
            vs._get_sparse_index()

        # Build should only happen once
        assert build_fn.call_count == 1

    def test_sparse_index_rebuilt_after_ttl(self):
        self._reset_module_state()
        import vectraiq.ai.vector_store as vs

        call_count = [0]
        def fake_build():
            call_count[0] += 1
            return MagicMock()

        # Set the built_at timestamp far in the past to simulate TTL expiry
        with patch.object(vs, "_build_sparse_index", side_effect=fake_build):
            vs._get_sparse_index()
            # Force TTL expiry
            vs._sparse_index_built_at = 0.0
            vs._get_sparse_index()

        assert call_count[0] == 2

    def test_invalidate_sparse_index_forces_rebuild(self):
        self._reset_module_state()
        import vectraiq.ai.vector_store as vs

        mock_index = MagicMock()
        call_count = [0]
        def fake_build():
            call_count[0] += 1
            return mock_index

        with patch.object(vs, "_build_sparse_index", side_effect=fake_build):
            vs._get_sparse_index()
            vs.invalidate_sparse_index()
            vs._get_sparse_index()

        assert call_count[0] == 2

    def test_invalidate_resets_built_at(self):
        self._reset_module_state()
        import vectraiq.ai.vector_store as vs

        with patch.object(vs, "_build_sparse_index", return_value=MagicMock()):
            vs._get_sparse_index()
            assert vs._sparse_index_built_at > 0

        vs.invalidate_sparse_index()
        assert vs._sparse_index is None
        assert vs._sparse_index_built_at == 0.0


class TestQdrantClientSingleton:
    def test_client_singleton_returns_same_instance(self):
        """The QdrantClient singleton must return the same object on repeated calls."""
        import vectraiq.ai.vector_store as vs

        mock_client = MagicMock()
        with patch("vectraiq.ai.vector_store.QdrantClient", return_value=mock_client):
            # Reset singleton
            vs._qdrant_client = None
            c1 = vs._get_qdrant_client()
            c2 = vs._get_qdrant_client()

        assert c1 is c2
