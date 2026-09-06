"""Unit tests for Phase 8's document deletion orchestration — mocked
stores, no DB/Qdrant/Neo4j/MinIO involved. Asserts the deletion order and
that the full-graph-rebuild path is invoked (the user's own resolved
decision over incremental provenance-tracked cleanup).
"""

from unittest.mock import MagicMock, call, patch

from app.services import document_deletion


def _make_document():
    document = MagicMock()
    document.id = "doc-1"
    document.minio_object_key = "hash123/sample.docx"
    return document


def test_delete_document_cleans_up_external_stores_before_postgres_row():
    document = _make_document()
    db = MagicMock()
    db.scalar.return_value = 2

    with (
        patch.object(document_deletion.vector_store, "delete_by_document") as mock_vector_delete,
        patch.object(document_deletion.vector_store, "get_qdrant_client") as mock_qdrant_client,
        patch.object(document_deletion.storage, "delete_document") as mock_storage_delete,
        patch.object(document_deletion.storage, "get_minio_client") as mock_minio_client,
        patch.object(document_deletion.graph_store, "get_neo4j_driver") as mock_driver_factory,
        patch.object(
            document_deletion.document_rebuild, "rebuild_graph_from_remaining_documents"
        ) as mock_rebuild,
    ):
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        manager = MagicMock()
        manager.attach_mock(mock_vector_delete, "vector_delete")
        manager.attach_mock(mock_storage_delete, "storage_delete")
        manager.attach_mock(db.delete, "db_delete")
        manager.attach_mock(db.commit, "db_commit")
        manager.attach_mock(mock_rebuild, "rebuild")

        result = document_deletion.delete_document(db, document)

        # Vector/MinIO cleanup and the Postgres delete happen before the
        # graph rebuild is triggered, and the Postgres row is committed
        # before the (potentially slow) rebuild starts.
        call_names = [c[0] for c in manager.mock_calls]
        assert call_names.index("vector_delete") < call_names.index("db_delete")
        assert call_names.index("storage_delete") < call_names.index("db_delete")
        assert call_names.index("db_commit") < call_names.index("rebuild")

        mock_vector_delete.assert_called_once_with(mock_qdrant_client.return_value, document.id)
        mock_storage_delete.assert_called_once_with(
            mock_minio_client.return_value, document.minio_object_key
        )
        db.delete.assert_called_once_with(document)
        mock_rebuild.assert_called_once_with(db, mock_driver)
        mock_driver.close.assert_called_once()
        assert result.remaining_document_count == 2


def test_delete_document_closes_driver_even_if_rebuild_raises():
    document = _make_document()
    db = MagicMock()

    with (
        patch.object(document_deletion.vector_store, "delete_by_document"),
        patch.object(document_deletion.vector_store, "get_qdrant_client"),
        patch.object(document_deletion.storage, "delete_document"),
        patch.object(document_deletion.storage, "get_minio_client"),
        patch.object(document_deletion.graph_store, "get_neo4j_driver") as mock_driver_factory,
        patch.object(
            document_deletion.document_rebuild,
            "rebuild_graph_from_remaining_documents",
            side_effect=RuntimeError("boom"),
        ),
    ):
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        try:
            document_deletion.delete_document(db, document)
        except RuntimeError:
            pass

        mock_driver.close.assert_called_once()


def test_rebuild_clears_graph_before_reprocessing_documents():
    from app.services import document_rebuild

    db = MagicMock()
    doc_a = MagicMock(id="a")
    doc_b = MagicMock(id="b")
    db.scalars.return_value = [doc_a, doc_b]
    driver = MagicMock()

    with (
        patch.object(document_rebuild.graph_store, "clear_entity_graph") as mock_clear,
        patch.object(document_rebuild.extraction, "extract_document_task") as mock_extract,
        patch.object(
            document_rebuild.extraction, "resolve_and_load_document_task"
        ) as mock_resolve,
    ):
        document_rebuild.rebuild_graph_from_remaining_documents(db, driver)

        mock_clear.assert_called_once_with(driver)
        assert mock_extract.call_args_list == [call("a"), call("b")]
        assert mock_resolve.call_args_list == [call(None, "a"), call(None, "b")]
