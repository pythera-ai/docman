"""
Test cases for Document Management API endpoints.
Tests all document-related operations including CRUD operations, file upload, and metadata management.
"""
import pytest
import json
import uuid
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from fastapi import HTTPException, UploadFile
from datetime import datetime
from typing import Dict, Any
import io

from src.api.routes.documents import router
from src.api.services.database_manager import DatabaseManager
from src.core.models import Document, DocumentMetadata
from src.core.exceptions import DatabaseConnectionException


class TestDocumentsUpload:
    """Test document upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db_manager, sample_session_data):
        """Test successful document upload."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        # Create mock upload file
        file_content = b"Test document content"
        file_obj = io.BytesIO(file_content)
        upload_file = UploadFile(filename="test.txt", file=file_obj)
        
        # Mock successful database response
        mock_db_manager.create_document.return_value = {
            "status": "success",
            "document_id": str(uuid.uuid4()),
            "message": "Document uploaded successfully"
        }
        
        # Import the function to test
        from src.api.routes.documents import upload_document
        
        # Act
        result = await upload_document(
            session_id=session_id,
            file=upload_file,
            metadata=None,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, Document)
        assert result.filename == "test.txt"
        assert result.session_id == session_id
        assert result.status == "uploaded"
        mock_db_manager.create_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_document_with_metadata(self, mock_db_manager, sample_session_data):
        """Test document upload with custom metadata."""
        # Arrange
        session_id = sample_session_data["session_id"]
        custom_metadata = json.dumps({"author": "test_user", "category": "technical"})
        
        file_content = b"Test document with metadata"
        file_obj = io.BytesIO(file_content)
        upload_file = UploadFile(filename="technical_doc.pdf", file=file_obj)
        
        mock_db_manager.create_document.return_value = {
            "status": "success",
            "document_id": str(uuid.uuid4())
        }
        
        from src.api.routes.documents import upload_document
        
        # Act
        result = await upload_document(
            session_id=session_id,
            file=upload_file,
            metadata=custom_metadata,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.filename == "technical_doc.pdf"
        
        # Verify create_document was called with metadata
        call_args = mock_db_manager.create_document.call_args
        assert call_args is not None
        assert "metadata" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_upload_document_database_error(self, mock_db_manager, sample_session_data):
        """Test document upload with database connection error."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        file_content = b"Test document content"
        file_obj = io.BytesIO(file_content)
        upload_file = UploadFile(filename="test.txt", file=file_obj)
        
        # Mock database connection error
        mock_db_manager.create_document.side_effect = DatabaseConnectionException(
            "Database connection failed", {"error_code": "DB_CONN_ERROR"}
        )
        
        from src.api.routes.documents import upload_document
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                session_id=session_id,
                file=upload_file,
                metadata=None,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_document_general_error(self, mock_db_manager, sample_session_data):
        """Test document upload with general error."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        file_content = b"Test document content"
        file_obj = io.BytesIO(file_content)
        upload_file = UploadFile(filename="test.txt", file=file_obj)
        
        # Mock general error
        mock_db_manager.create_document.side_effect = Exception("Unexpected error")
        
        from src.api.routes.documents import upload_document
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                session_id=session_id,
                file=upload_file,
                metadata=None,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to get document info" in str(exc_info.value.detail)


class TestDocumentsValidation:
    """Test document validation functionality."""

    @pytest.mark.asyncio
    async def test_validate_file_upload_success(self, mock_db_manager):
        """Test successful file validation."""
        # Arrange
        files = []
        for i in range(2):
            file_content = f"Test file content {i+1}".encode()
            file_obj = io.BytesIO(file_content)
            files.append(UploadFile(filename=f"test_{i+1}.txt", file=file_obj))
        
        # Mock MinIO client validation
        mock_db_manager.minio_client.validate_file_request.return_value = {
            "status": "success",
            "valid_files": 2,
            "invalid_files": 0,
            "total_size": 1024,
            "validation_results": []
        }
        
        from src.api.routes.documents import validate_file_upload
        
        # Act
        result = await validate_file_upload(
            files=files,
            max_files=10,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["status"] == "success"
        assert result["valid_files"] == 2
        mock_db_manager.minio_client.validate_file_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_file_upload_no_minio(self, mock_db_manager):
        """Test file validation when MinIO client is unavailable."""
        # Arrange
        files = [UploadFile(filename="test.txt", file=io.BytesIO(b"test content"))]
        mock_db_manager.minio_client = None
        
        from src.api.routes.documents import validate_file_upload
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await validate_file_upload(
                files=files,
                max_files=10,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "MinIO client not available" in str(exc_info.value.detail)


class TestDocumentsRetrieval:
    """Test document retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_session_documents_success(self, mock_db_manager, sample_session_data):
        """Test successful retrieval of session documents."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        mock_db_manager.get_session_documents.return_value = {
            "documents": [
                {"document_id": str(uuid.uuid4()), "filename": "doc1.pdf"},
                {"document_id": str(uuid.uuid4()), "filename": "doc2.txt"}
            ],
            "total_found": 2,
            "offset": 0,
            "limit": 100
        }
        
        from src.api.routes.documents import get_session_documents
        
        # Act
        result = await get_session_documents(
            session_id=session_id,
            limit=100,
            offset=0,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["total_found"] == 2
        assert len(result["documents"]) == 2
        mock_db_manager.get_session_documents.assert_called_once_with(
            session_id=session_id,
            limit=100,
            offset=0
        )

    @pytest.mark.asyncio
    async def test_get_session_documents_database_error(self, mock_db_manager, sample_session_data):
        """Test session documents retrieval with database error."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        mock_db_manager.get_session_documents.return_value = {
            "error": "Database query failed"
        }
        
        from src.api.routes.documents import get_session_documents
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_session_documents(
                session_id=session_id,
                limit=100,
                offset=0,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to get session documents" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_documents_success(self, mock_db_manager):
        """Test successful document listing."""
        # Arrange
        mock_db_manager.minio_client.search.return_value = {
            "documents": [
                {"document_id": str(uuid.uuid4()), "filename": "doc1.pdf"},
                {"document_id": str(uuid.uuid4()), "filename": "doc2.txt"},
                {"document_id": str(uuid.uuid4()), "filename": "doc3.docx"}
            ],
            "processing_time_ms": 45
        }
        
        from src.api.routes.documents import list_documents
        
        # Act
        result = await list_documents(
            filename_pattern="*.pdf",
            include_metadata=True,
            limit=10,
            offset=0,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert "documents" in result
        assert "total_found" in result
        assert result["returned_count"] <= 10
        mock_db_manager.minio_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_documents_no_minio(self, mock_db_manager):
        """Test document listing when MinIO client is unavailable."""
        # Arrange
        mock_db_manager.minio_client = None
        
        from src.api.routes.documents import list_documents
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await list_documents(
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "MinIO client not available" in str(exc_info.value.detail)


class TestDocumentsDownload:
    """Test document download functionality."""

    @pytest.mark.asyncio
    async def test_download_document_success(self, mock_db_manager):
        """Test successful document download."""
        # Arrange
        document_id = str(uuid.uuid4())
        file_content = b"Test document content for download"
        
        mock_db_manager.download_document.return_value = {
            "file_content": file_content,
            "filename": "test_document.txt",
            "content_type": "text/plain"
        }
        
        from src.api.routes.documents import download_document
        
        # Act
        result = await download_document(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.media_type == "text/plain"
        assert result.headers["Content-Disposition"] == 'attachment; filename="test_document.txt"'
        assert result.headers["Content-Length"] == str(len(file_content))
        mock_db_manager.download_document.assert_called_once_with(document_id=document_id)

    @pytest.mark.asyncio
    async def test_download_document_not_found(self, mock_db_manager):
        """Test document download when document is not found."""
        # Arrange
        document_id = str(uuid.uuid4())
        
        mock_db_manager.download_document.return_value = {
            "error": "Document not found"
        }
        
        from src.api.routes.documents import download_document
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await download_document(
                document_id=document_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 404
        assert f"Document not found: {document_id}" in str(exc_info.value.detail)


class TestDocumentsUpdate:
    """Test document update and metadata operations."""

    @pytest.mark.asyncio
    async def test_update_document_metadata_success(self, mock_db_manager):
        """Test successful document metadata update."""
        # Arrange
        document_id = str(uuid.uuid4())
        new_metadata = {"updated_by": "test_user", "version": "2.0"}
        
        mock_db_manager.update_document.return_value = {
            "status": "success",
            "updated_fields": ["metadata"]
        }
        
        from src.api.routes.documents import update_document_metadata
        
        # Act
        result = await update_document_metadata(
            document_id=document_id,
            metadata=new_metadata,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["message"] == "Document metadata updated successfully"
        assert result["document_id"] == document_id
        mock_db_manager.update_document.assert_called_once_with(
            document_id=document_id,
            updates=new_metadata
        )

    @pytest.mark.asyncio
    async def test_get_document_metadata_success(self, mock_db_manager, sample_document_metadata):
        """Test successful document metadata retrieval."""
        # Arrange
        document_id = sample_document_metadata["document_id"]
        
        mock_db_manager.get_document.return_value = sample_document_metadata
        
        from src.api.routes.documents import get_document_metadata
        
        # Act
        result = await get_document_metadata(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, DocumentMetadata)
        assert result.document_id == document_id
        assert result.filename == sample_document_metadata["filename"]
        mock_db_manager.get_document.assert_called_once_with(document_id=document_id)

    @pytest.mark.asyncio
    async def test_get_document_metadata_not_found_fallback_minio(self, mock_db_manager):
        """Test document metadata retrieval with fallback to MinIO."""
        # Arrange
        document_id = str(uuid.uuid4())
        
        # Mock PostgreSQL returning None (not found)
        mock_db_manager.get_document.return_value = None
        
        # Mock MinIO returning document info
        minio_info = {
            "filename": "test_from_minio.pdf",
            "file_size": 2048,
            "content_type": "application/pdf",
            "upload_time": datetime.utcnow().isoformat(),
            "last_modified": datetime.utcnow().isoformat(),
            "metadata": {"source": "minio"}
        }
        mock_db_manager.minio_client.get_document_info.return_value = minio_info
        
        from src.api.routes.documents import get_document_metadata
        
        # Act
        result = await get_document_metadata(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, DocumentMetadata)
        assert result.filename == "test_from_minio.pdf"
        assert result.file_size == 2048


class TestDocumentsDeletion:
    """Test document deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_document_success(self, mock_db_manager):
        """Test successful document deletion."""
        # Arrange
        document_id = str(uuid.uuid4())
        
        mock_db_manager.delete_document.return_value = {
            "status": "success",
            "deleted_from": ["minio", "postgres", "qdrant"]
        }
        
        from src.api.routes.documents import delete_document
        
        # Act
        result = await delete_document(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["message"] == "Document deleted successfully"
        assert result["document_id"] == document_id
        mock_db_manager.delete_document.assert_called_once_with(document_id=document_id)

    @pytest.mark.asyncio
    async def test_delete_document_database_error(self, mock_db_manager):
        """Test document deletion with database error."""
        # Arrange
        document_id = str(uuid.uuid4())
        
        mock_db_manager.delete_document.side_effect = DatabaseConnectionException(
            "Database connection lost", {"error_code": "CONNECTION_LOST"}
        )
        
        from src.api.routes.documents import delete_document
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_document(
                document_id=document_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)


class TestDocumentsDuplicateCheck:
    """Test document duplicate checking functionality."""

    @pytest.mark.asyncio
    async def test_check_duplicate_document_found(self, mock_db_manager):
        """Test duplicate check when duplicate is found."""
        # Arrange
        file_hash = "abc123def456"
        
        duplicate_info = {
            "document_id": str(uuid.uuid4()),
            "filename": "existing_document.pdf",
            "upload_time": datetime.utcnow().isoformat()
        }
        mock_db_manager.minio_client.check_duplicate.return_value = duplicate_info
        
        from src.api.routes.documents import check_duplicate_document
        
        # Act
        result = await check_duplicate_document(
            file_hash=file_hash,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["duplicate_found"] is True
        assert result["existing_document"] == duplicate_info
        mock_db_manager.minio_client.check_duplicate.assert_called_once_with(
            file_hash=file_hash,
            bucket_name=mock_db_manager.minio_client.check_duplicate.call_args.kwargs["bucket_name"]
        )

    @pytest.mark.asyncio
    async def test_check_duplicate_document_not_found(self, mock_db_manager):
        """Test duplicate check when no duplicate is found."""
        # Arrange
        file_hash = "unique123hash456"
        
        mock_db_manager.minio_client.check_duplicate.return_value = None
        
        from src.api.routes.documents import check_duplicate_document
        
        # Act
        result = await check_duplicate_document(
            file_hash=file_hash,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["duplicate_found"] is False
        assert result["message"] == "No duplicate found"


class TestDocumentsInfo:
    """Test document info functionality."""

    @pytest.mark.asyncio
    async def test_get_document_info_success(self, mock_db_manager):
        """Test successful document info retrieval."""
        # Arrange
        document_id = str(uuid.uuid4())
        
        document_info = {
            "document_id": document_id,
            "filename": "detailed_document.pdf",
            "file_size": 4096,
            "content_type": "application/pdf",
            "upload_time": datetime.utcnow().isoformat(),
            "metadata": {"pages": 25, "author": "test_author"}
        }
        mock_db_manager.minio_client.get_document_info.return_value = document_info
        
        from src.api.routes.documents import get_document_info
        
        # Act
        result = await get_document_info(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result == document_info
        mock_db_manager.minio_client.get_document_info.assert_called_once_with(
            document_id=document_id,
            bucket_name=mock_db_manager.minio_client.get_document_info.call_args.kwargs["bucket_name"]
        )

    @pytest.mark.asyncio
    async def test_get_document_info_not_found(self, mock_db_manager):
        """Test document info retrieval when document is not found."""
        # Arrange
        document_id = str(uuid.uuid4())
        
        mock_db_manager.minio_client.get_document_info.return_value = None
        
        from src.api.routes.documents import get_document_info
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_document_info(
                document_id=document_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 404
        assert f"Document not found: {document_id}" in str(exc_info.value.detail)


@pytest.mark.integration
class TestDocumentsIntegration:
    """Integration tests for document management workflow."""

    @pytest.mark.asyncio
    async def test_document_lifecycle(self, mock_db_manager, sample_session_data):
        """Test complete document lifecycle: upload -> retrieve -> update -> delete."""
        # Import functions
        from src.api.routes.documents import (
            upload_document, get_document_metadata, 
            update_document_metadata, delete_document
        )
        
        # Setup
        session_id = sample_session_data["session_id"]
        document_id = str(uuid.uuid4())
        
        # Mock successful operations
        mock_db_manager.create_document.return_value = {
            "status": "success",
            "document_id": document_id
        }
        
        mock_db_manager.get_document.return_value = {
            "document_id": document_id,
            "filename": "lifecycle_test.pdf",
            "file_size": 1024,
            "content_type": "application/pdf",
            "file_hash": "test_hash",
            "chunks_count": 0,
            "processing_status": "uploaded",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {}
        }
        
        mock_db_manager.update_document.return_value = {"status": "success"}
        mock_db_manager.delete_document.return_value = {"status": "success"}
        
        # 1. Upload document
        file_content = b"Test document for lifecycle"
        file_obj = io.BytesIO(file_content)
        upload_file = UploadFile(filename="lifecycle_test.pdf", file=file_obj)
        
        upload_result = await upload_document(
            session_id=session_id,
            file=upload_file,
            metadata=None,
            db_manager=mock_db_manager
        )
        
        assert upload_result.filename == "lifecycle_test.pdf"
        
        # 2. Retrieve metadata
        metadata = await get_document_metadata(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        assert metadata.document_id == document_id
        
        # 3. Update metadata
        new_metadata = {"status": "processed", "version": "1.1"}
        update_result = await update_document_metadata(
            document_id=document_id,
            metadata=new_metadata,
            db_manager=mock_db_manager
        )
        
        assert "updated successfully" in update_result["message"]
        
        # 4. Delete document
        delete_result = await delete_document(
            document_id=document_id,
            db_manager=mock_db_manager
        )
        
        assert "deleted successfully" in delete_result["message"]
        
        # Verify all operations were called
        mock_db_manager.create_document.assert_called_once()
        mock_db_manager.get_document.assert_called_once()
        mock_db_manager.update_document.assert_called_once()
        mock_db_manager.delete_document.assert_called_once()
