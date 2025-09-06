"""
Test cases for Chunks Management API endpoints.
Tests all chunk-related operations including CRUD operations, vector search, and session integration.
"""
import pytest
import uuid
from unittest.mock import Mock, AsyncMock
from fastapi import HTTPException
from datetime import datetime
from typing import Dict, Any, List

from src.api.routes.chunks import router
from src.api.services.database_manager import DatabaseManager
from src.core.models import (
    ChunkUpdateRequest, ChunkDeleteRequest, ChunkUploadRequest, ChunkUploadResponse,
    ChunkOperationResponse, SearchRequest, SearchResponse, SearchResult
)
from src.core.exceptions import DatabaseConnectionException


class TestChunksUpload:
    """Test chunks upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_chunks_success(self, mock_db_manager, sample_chunks_data):
        """Test successful chunks upload."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        # Create ChunkUploadRequest from sample data
        chunks = []
        for chunk_data in sample_chunks_data:
            chunk = Mock()
            chunk.vector = chunk_data["vector"]
            chunk.document_id = chunk_data["document_id"]
            chunk.document_title = chunk_data["document_title"]
            chunk.chunk_text = chunk_data["chunk_text"]
            chunk.page_number = chunk_data["page_number"]
            chunk.metadata = chunk_data["metadata"]
            chunks.append(chunk)
        
        request = Mock()
        request.chunks = chunks
        
        # Mock successful database response
        mock_db_manager.create_chunks.return_value = {
            "status": "success",
            "points_processed": len(chunks),
            "failed_points": None
        }
        
        from src.api.routes.chunks import upload_chunks
        
        # Act
        result = await upload_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, ChunkUploadResponse)
        assert result.status == "success"
        assert result.chunks_processed == len(chunks)
        assert result.failed_chunks is None
        mock_db_manager.create_chunks.assert_called_once()
        
        # Verify chunks data preparation
        call_args = mock_db_manager.create_chunks.call_args.kwargs
        chunks_data = call_args["chunks"]
        assert len(chunks_data) == len(chunks)
        
        # Verify first chunk structure
        first_chunk = chunks_data[0]
        assert "vector" in first_chunk
        assert "payload" in first_chunk
        assert first_chunk["payload"]["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_upload_chunks_partial_failure(self, mock_db_manager, sample_chunks_data):
        """Test chunks upload with partial failures."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        chunks = []
        for chunk_data in sample_chunks_data[:2]:  # Only use first 2 chunks
            chunk = Mock()
            chunk.vector = chunk_data["vector"]
            chunk.document_id = chunk_data["document_id"]
            chunk.document_title = chunk_data["document_title"]
            chunk.chunk_text = chunk_data["chunk_text"]
            chunk.page_number = chunk_data["page_number"]
            chunk.metadata = chunk_data["metadata"]
            chunks.append(chunk)
        
        request = Mock()
        request.chunks = chunks
        
        # Mock partial failure response
        mock_db_manager.create_chunks.return_value = {
            "status": "partial_failure",
            "points_processed": 1,
            "failed_points": [{"error": "Vector dimension mismatch"}],
            "message": "Some chunks failed to upload"
        }
        
        from src.api.routes.chunks import upload_chunks
        
        # Act
        result = await upload_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "partial_failure"
        assert result.chunks_processed == 1
        assert len(result.failed_chunks) == 1
        assert "Vector dimension mismatch" in result.failed_chunks[0]["error"]

    @pytest.mark.asyncio
    async def test_upload_chunks_database_error(self, mock_db_manager, sample_chunks_data):
        """Test chunks upload with database connection error."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        chunk = Mock()
        chunk.vector = sample_chunks_data[0]["vector"]
        chunk.document_id = sample_chunks_data[0]["document_id"]
        chunk.document_title = sample_chunks_data[0]["document_title"]
        chunk.chunk_text = sample_chunks_data[0]["chunk_text"]
        chunk.page_number = sample_chunks_data[0]["page_number"]
        chunk.metadata = sample_chunks_data[0]["metadata"]
        
        request = Mock()
        request.chunks = [chunk]
        
        # Mock database connection error
        mock_db_manager.create_chunks.side_effect = DatabaseConnectionException(
            "Qdrant connection failed", {"service": "qdrant"}
        )
        
        from src.api.routes.chunks import upload_chunks
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await upload_chunks(
                session_id=session_id,
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_chunks_general_error(self, mock_db_manager, sample_chunks_data):
        """Test chunks upload with general error."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        chunk = Mock()
        chunk.vector = sample_chunks_data[0]["vector"]
        chunk.document_id = sample_chunks_data[0]["document_id"]
        chunk.document_title = sample_chunks_data[0]["document_title"]
        chunk.chunk_text = sample_chunks_data[0]["chunk_text"]
        chunk.page_number = sample_chunks_data[0]["page_number"]
        chunk.metadata = sample_chunks_data[0]["metadata"]
        
        request = Mock()
        request.chunks = [chunk]
        
        # Mock general error
        mock_db_manager.create_chunks.side_effect = Exception("Unexpected error during chunk upload")
        
        from src.api.routes.chunks import upload_chunks
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await upload_chunks(
                session_id=session_id,
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to upload chunks" in str(exc_info.value.detail)


class TestChunksSearch:
    """Test chunks search functionality."""

    @pytest.mark.asyncio
    async def test_search_chunks_success(self, mock_db_manager, sample_search_request):
        """Test successful chunks search."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        request = Mock()
        request.query_vector = sample_search_request["query_vector"]
        request.limit = sample_search_request["limit"]
        request.filters = sample_search_request["filters"]
        
        # Mock successful search results
        search_results = [
            {
                "id": str(uuid.uuid4()),
                "score": 0.95,
                "payload": {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": str(uuid.uuid4()),
                    "doc_title": "Test Document 1",
                    "chunk_content": "This is a test chunk content",
                    "page": 1,
                    "section": "introduction"
                }
            },
            {
                "id": str(uuid.uuid4()),
                "score": 0.87,
                "payload": {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": str(uuid.uuid4()),
                    "doc_title": "Test Document 2",
                    "chunk_content": "Another test chunk content",
                    "page": 3,
                    "section": "conclusion"
                }
            }
        ]
        
        mock_db_manager.get_chunks.return_value = {
            "chunks": search_results,
            "total_found": 2
        }
        
        from src.api.routes.chunks import search_chunks
        
        # Act
        result = await search_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, SearchResponse)
        assert result.query_vector == sample_search_request["query_vector"]
        assert len(result.results) == 2
        assert result.total_results == 2
        
        # Verify first result structure
        first_result = result.results[0]
        assert isinstance(first_result, SearchResult)
        assert first_result.similarity_score == 0.95
        assert first_result.document_title == "Test Document 1"
        assert first_result.chunk_text == "This is a test chunk content"
        
        # Verify search parameters were passed correctly
        mock_db_manager.get_chunks.assert_called_once()
        call_args = mock_db_manager.get_chunks.call_args.kwargs
        assert call_args["query_vector"] == sample_search_request["query_vector"]
        assert call_args["limit"] == sample_search_request["limit"]

    @pytest.mark.asyncio
    async def test_search_chunks_empty_results(self, mock_db_manager, sample_search_request):
        """Test chunks search with empty results."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        request = Mock()
        request.query_vector = sample_search_request["query_vector"]
        request.limit = sample_search_request["limit"]
        request.filters = sample_search_request["filters"]
        
        # Mock empty search results
        mock_db_manager.get_chunks.return_value = {
            "chunks": [],
            "total_found": 0
        }
        
        from src.api.routes.chunks import search_chunks
        
        # Act
        result = await search_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, SearchResponse)
        assert len(result.results) == 0
        assert result.total_results == 0

    @pytest.mark.asyncio
    async def test_search_chunks_with_filters(self, mock_db_manager):
        """Test chunks search with specific filters."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        request = Mock()
        request.query_vector = [0.2] * 384
        request.limit = 10
        request.filters = {
            "document_type": "pdf",
            "language": "en",
            "page_range": {"min": 1, "max": 10}
        }
        
        mock_db_manager.get_chunks.return_value = {
            "chunks": [{
                "id": str(uuid.uuid4()),
                "score": 0.92,
                "payload": {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": str(uuid.uuid4()),
                    "doc_title": "Filtered Document",
                    "chunk_content": "Filtered content",
                    "page": 5
                }
            }],
            "total_found": 1
        }
        
        from src.api.routes.chunks import search_chunks
        
        # Act
        result = await search_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert len(result.results) == 1
        
        # Verify filters were passed to database manager
        call_args = mock_db_manager.get_chunks.call_args.kwargs
        search_params = call_args["filters"]
        assert "document_type" in search_params
        assert "language" in search_params
        assert search_params["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_search_chunks_database_error(self, mock_db_manager, sample_search_request):
        """Test chunks search with database connection error."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        request = Mock()
        request.query_vector = sample_search_request["query_vector"]
        request.limit = sample_search_request["limit"]
        request.filters = sample_search_request["filters"]
        
        # Mock database connection error
        mock_db_manager.get_chunks.side_effect = DatabaseConnectionException(
            "Qdrant search service unavailable", {"service": "qdrant"}
        )
        
        from src.api.routes.chunks import search_chunks
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await search_chunks(
                session_id=session_id,
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)


class TestChunksUpdate:
    """Test chunks update functionality."""

    @pytest.mark.asyncio
    async def test_update_chunks_success(self, mock_db_manager):
        """Test successful chunks update."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        chunk_updates = []
        for i in range(2):
            update = Mock()
            update.chunk_id = str(uuid.uuid4())
            update.vector = [0.3 + i * 0.1] * 384
            update.chunk_text = f"Updated chunk text {i+1}"
            update.metadata = {"updated": True, "version": i+1}
            chunk_updates.append(update)
        
        # Mock successful update response
        mock_db_manager.update_chunks.return_value = {
            "status": "success",
            "points_updated": len(chunk_updates),
            "failed_updates": None
        }
        
        from src.api.routes.chunks import update_chunks
        
        # Act
        result = await update_chunks(
            session_id=session_id,
            updates=chunk_updates,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, ChunkOperationResponse)
        assert result.status == "success"
        assert result.chunks_affected == len(chunk_updates)
        assert result.errors is None
        mock_db_manager.update_chunks.assert_called_once()
        
        # Verify update data structure
        call_args = mock_db_manager.update_chunks.call_args.kwargs
        update_points = call_args["chunks"]
        assert len(update_points) == len(chunk_updates)
        
        # Verify first update structure
        first_update = update_points[0]
        assert "id" in first_update
        assert "vector" in first_update
        assert "payload" in first_update
        assert first_update["payload"]["session_id"] == session_id
        assert first_update["payload"]["chunk_content"] == "Updated chunk text 1"

    @pytest.mark.asyncio
    async def test_update_chunks_partial_failure(self, mock_db_manager):
        """Test chunks update with partial failures."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        update = ChunkUpdateRequest(
            chunk_id=str(uuid.uuid4()),
            vector=[0.4] * 384,
            chunk_text="Updated text",
            metadata={"updated": True}
        )
        
        # Mock partial failure response
        mock_db_manager.update_chunks.return_value = {
            "status": "partial_failure",
            "points_updated": 0,
            "failed_updates": [{"error": "Chunk not found"}]
        }
        
        from src.api.routes.chunks import update_chunks
        
        # Act
        result = await update_chunks(
            session_id=session_id,
            updates=[update],
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "partial_failure"
        assert result.chunks_affected == 0
        assert result.errors is not None
        assert len(result.errors) == 1
        assert result.errors[0]["error"] == "Chunk not found"

    @pytest.mark.asyncio
    async def test_update_chunks_metadata_only(self, mock_db_manager):
        """Test chunks update with metadata only (no vector update)."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        update = Mock()
        update.chunk_id = str(uuid.uuid4())
        update.vector = None  # No vector update
        update.chunk_text = None  # No text update
        update.metadata = {"priority": "high", "reviewed": True}
        
        mock_db_manager.update_chunks.return_value = {
            "status": "success",
            "points_updated": 1
        }
        
        from src.api.routes.chunks import update_chunks
        
        # Act
        result = await update_chunks(
            session_id=session_id,
            updates=[update],
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "success"
        assert result.chunks_affected == 1
        
        # Verify only metadata was updated
        call_args = mock_db_manager.update_chunks.call_args.kwargs
        update_points = call_args["chunks"]
        first_update = update_points[0]
        
        assert "vector" not in first_update  # No vector update
        assert "payload" in first_update
        assert first_update["payload"]["priority"] == "high"
        assert first_update["payload"]["reviewed"] is True

    @pytest.mark.asyncio
    async def test_update_chunks_database_error(self, mock_db_manager):
        """Test chunks update with database connection error."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        update = Mock()
        update.chunk_id = str(uuid.uuid4())
        update.vector = [0.5] * 384
        update.chunk_text = "Test update"
        update.metadata = {}
        
        # Mock database connection error
        mock_db_manager.update_chunks.side_effect = DatabaseConnectionException(
            "Qdrant update service failed", {"operation": "update"}
        )
        
        from src.api.routes.chunks import update_chunks
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await update_chunks(
                session_id=session_id,
                updates=[update],
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)


class TestChunksDeletion:
    """Test chunks deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_chunks_success(self, mock_db_manager):
        """Test successful chunks deletion."""
        # Arrange
        session_id = str(uuid.uuid4())
        chunk_ids = [str(uuid.uuid4()) for _ in range(3)]
        
        request = Mock()
        request.chunk_ids = chunk_ids
        
        # Mock successful deletion response
        mock_db_manager.delete_chunks.return_value = {
            "status": "success",
            "errors": None
        }
        
        from src.api.routes.chunks import delete_chunks
        
        # Act
        result = await delete_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, ChunkOperationResponse)
        assert result.status == "success"
        assert result.chunks_affected == len(chunk_ids)
        assert result.errors is None
        mock_db_manager.delete_chunks.assert_called_once_with(chunk_ids=chunk_ids)

    @pytest.mark.asyncio
    async def test_delete_chunks_partial_failure(self, mock_db_manager):
        """Test chunks deletion with partial failures."""
        # Arrange
        session_id = str(uuid.uuid4())
        chunk_ids = [str(uuid.uuid4()) for _ in range(2)]
        
        request = ChunkDeleteRequest(chunk_ids=chunk_ids)
        
        # Mock partial failure response
        mock_db_manager.delete_chunks.return_value = {
            "status": "partial_failure",
            "errors": [{"error": "Chunk not found: " + chunk_ids[1]}]
        }
        
        from src.api.routes.chunks import delete_chunks
        
        # Act
        result = await delete_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "partial_failure"
        assert result.chunks_affected == len(chunk_ids)
        assert result.errors is not None
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_delete_chunks_empty_list(self, mock_db_manager):
        """Test chunks deletion with empty chunk ID list."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        request = Mock()
        request.chunk_ids = []
        
        mock_db_manager.delete_chunks.return_value = {
            "status": "success",
            "errors": None
        }
        
        from src.api.routes.chunks import delete_chunks
        
        # Act
        result = await delete_chunks(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "success"
        assert result.chunks_affected == 0
        mock_db_manager.delete_chunks.assert_called_once_with(chunk_ids=[])

    @pytest.mark.asyncio
    async def test_delete_chunks_database_error(self, mock_db_manager):
        """Test chunks deletion with database connection error."""
        # Arrange
        session_id = str(uuid.uuid4())
        chunk_ids = [str(uuid.uuid4())]
        
        request = Mock()
        request.chunk_ids = chunk_ids
        
        # Mock database connection error
        mock_db_manager.delete_chunks.side_effect = DatabaseConnectionException(
            "Qdrant delete service unavailable", {"operation": "delete"}
        )
        
        from src.api.routes.chunks import delete_chunks
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_chunks(
                session_id=session_id,
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_chunks_general_error(self, mock_db_manager):
        """Test chunks deletion with general error."""
        # Arrange
        session_id = str(uuid.uuid4())
        chunk_ids = [str(uuid.uuid4())]
        
        request = Mock()
        request.chunk_ids = chunk_ids
        
        # Mock general error
        mock_db_manager.delete_chunks.side_effect = Exception("Unexpected deletion error")
        
        from src.api.routes.chunks import delete_chunks
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_chunks(
                session_id=session_id,
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to delete chunks" in str(exc_info.value.detail)


@pytest.mark.integration
class TestChunksIntegration:
    """Integration tests for chunks management workflow."""

    @pytest.mark.asyncio
    async def test_chunks_lifecycle(self, mock_db_manager, sample_chunks_data):
        """Test complete chunks lifecycle: upload -> search -> update -> delete."""
        # Import functions
        from src.api.routes.chunks import (
            upload_chunks, search_chunks, update_chunks, delete_chunks
        )
        
        # Setup
        session_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())
        
        # Mock successful operations
        mock_db_manager.create_chunks.return_value = {
            "status": "success",
            "points_processed": 3,
            "failed_points": None
        }
        
        mock_db_manager.get_chunks.return_value = {
            "chunks": [
                {
                    "id": str(uuid.uuid4()),
                    "score": 0.95,
                    "payload": {
                        "chunk_id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "doc_title": "Test Document",
                        "chunk_content": "Test chunk content",
                        "page": 1
                    }
                }
            ],
            "total_found": 1
        }
        
        mock_db_manager.update_chunks.return_value = {
            "status": "success",
            "points_updated": 1
        }
        
        mock_db_manager.delete_chunks.return_value = {
            "status": "success",
            "errors": None
        }
        
        # 1. Upload chunks
        chunks = []
        for chunk_data in sample_chunks_data:
            chunk = Mock()
            chunk.vector = chunk_data["vector"]
            chunk.document_id = document_id
            chunk.document_title = chunk_data["document_title"]
            chunk.chunk_text = chunk_data["chunk_text"]
            chunk.page_number = chunk_data["page_number"]
            chunk.metadata = chunk_data["metadata"]
            chunks.append(chunk)
        
        upload_request = Mock()
        upload_request.chunks = chunks
        
        upload_result = await upload_chunks(
            session_id=session_id,
            request=upload_request,
            db_manager=mock_db_manager
        )
        
        assert upload_result.status == "success"
        assert upload_result.chunks_processed == 3
        
        # 2. Search chunks
        search_request = Mock()
        search_request.query_vector = [0.1] * 384
        search_request.limit = 5
        search_request.filters = {"document_id": document_id}
        
        search_result = await search_chunks(
            session_id=session_id,
            request=search_request,
            db_manager=mock_db_manager
        )
        
        assert len(search_result.results) == 1
        assert search_result.total_results == 1
        
        # 3. Update chunks
        chunk_id = search_result.results[0].chunk_id
        
        update = Mock()
        update.chunk_id = chunk_id
        update.vector = [0.2] * 384
        update.chunk_text = "Updated chunk content"
        update.metadata = {"updated": True}
        
        update_result = await update_chunks(
            session_id=session_id,
            updates=[update],
            db_manager=mock_db_manager
        )
        
        assert update_result.status == "success"
        assert update_result.chunks_affected == 1
        
        # 4. Delete chunks
        delete_request = Mock()
        delete_request.chunk_ids = [chunk_id]
        
        delete_result = await delete_chunks(
            session_id=session_id,
            request=delete_request,
            db_manager=mock_db_manager
        )
        
        assert delete_result.status == "success"
        assert delete_result.chunks_affected == 1
        
        # Verify all operations were called
        mock_db_manager.create_chunks.assert_called_once()
        mock_db_manager.get_chunks.assert_called_once()
        mock_db_manager.update_chunks.assert_called_once()
        mock_db_manager.delete_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_search_filtering_by_session(self, mock_db_manager):
        """Test that chunks search properly filters by session."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        search_request = Mock()
        search_request.query_vector = [0.3] * 384
        search_request.limit = 10
        search_request.filters = {"document_type": "pdf"}
        
        mock_db_manager.get_chunks.return_value = {
            "chunks": [],
            "total_found": 0
        }
        
        from src.api.routes.chunks import search_chunks
        
        # Act
        await search_chunks(
            session_id=session_id,
            request=search_request,
            db_manager=mock_db_manager
        )
        
        # Assert
        call_args = mock_db_manager.get_chunks.call_args.kwargs
        search_params = call_args["filters"]
        
        # Verify session_id was added to search filters
        assert search_params["session_id"] == session_id
        assert search_params["document_type"] == "pdf"  # Original filter preserved

    @pytest.mark.asyncio
    async def test_chunks_batch_operations(self, mock_db_manager):
        """Test batch operations on chunks."""
        # Import functions
        from src.api.routes.chunks import upload_chunks, update_chunks, delete_chunks
        
        # Setup
        session_id = str(uuid.uuid4())
        
        # Create large batch of chunks
        chunks = []
        chunk_ids = []
        for i in range(10):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            
            chunk = Mock()
            chunk.vector = [0.1 + i * 0.01] * 384
            chunk.document_id = str(uuid.uuid4())
            chunk.document_title = f"Batch Document {i+1}"
            chunk.chunk_text = f"Batch chunk content {i+1}"
            chunk.page_number = i + 1
            chunk.metadata = {"batch": True, "index": i}
            chunks.append(chunk)
        
        # Mock successful batch operations
        mock_db_manager.create_chunks.return_value = {
            "status": "success",
            "points_processed": 10
        }
        
        mock_db_manager.update_chunks.return_value = {
            "status": "success",
            "points_updated": 10
        }
        
        mock_db_manager.delete_chunks.return_value = {
            "status": "success"
        }
        
        # Test batch upload
        upload_request = Mock()
        upload_request.chunks = chunks
        
        upload_result = await upload_chunks(
            session_id=session_id,
            request=upload_request,
            db_manager=mock_db_manager
        )
        
        assert upload_result.chunks_processed == 10
        
        # Test batch update
        updates = []
        for i, chunk_id in enumerate(chunk_ids):
            update = Mock()
            update.chunk_id = chunk_id
            update.vector = None
            update.chunk_text = None
            update.metadata = {"updated": True, "batch_index": i}
            updates.append(update)
        
        update_result = await update_chunks(
            session_id=session_id,
            updates=updates,
            db_manager=mock_db_manager
        )
        
        assert update_result.chunks_affected == 10
        
        # Test batch delete
        delete_request = Mock()
        delete_request.chunk_ids = chunk_ids
        
        delete_result = await delete_chunks(
            session_id=session_id,
            request=delete_request,
            db_manager=mock_db_manager
        )
        
        assert delete_result.chunks_affected == 10
