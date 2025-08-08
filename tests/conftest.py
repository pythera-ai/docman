"""
Pytest configuration and shared fixtures for Document Management System tests.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
from datetime import datetime, timedelta
from typing import Dict, Any, List
import uuid
import io

from src.api.main import app
from src.api.services.database_manager import DatabaseManager
from src.core.models import SessionInfo, Document, DocumentMetadata


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create a TestClient instance for synchronous testing."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client():
    """Create an AsyncClient instance for async testing."""
    from httpx import AsyncClient
    async with AsyncClient(base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_db_manager():
    """Create a mock DatabaseManager for testing."""
    mock_manager = Mock(spec=DatabaseManager)
    mock_manager.is_healthy = Mock(return_value={
        "overall": True,
        "minio": True,
        "qdrant": True,
        "postgres": True
    })
    
    # Mock async methods
    mock_manager.initialize = AsyncMock()
    mock_manager.cleanup = AsyncMock()
    mock_manager.create_session = AsyncMock()
    mock_manager.get_session = AsyncMock()
    mock_manager.update_session = AsyncMock()
    mock_manager.delete_session = AsyncMock()
    mock_manager.get_user_sessions = AsyncMock()
    mock_manager.expire_old_sessions = AsyncMock()
    mock_manager.get_session_documents = AsyncMock()
    # Mock other database operations
    mock_manager.create_document = AsyncMock()
    mock_manager.get_document = AsyncMock()
    mock_manager.update_document = AsyncMock()
    mock_manager.delete_document = AsyncMock()
    mock_manager.get_session = AsyncMock()
    mock_manager.search_documents = AsyncMock()
    mock_manager.download_document = AsyncMock()
    mock_manager.create_session = AsyncMock()
    mock_manager.update_session = AsyncMock()
    mock_manager.delete_session = AsyncMock()
    mock_manager.create_chunks = AsyncMock()
    mock_manager.get_chunks = AsyncMock()
    mock_manager.update_chunks = AsyncMock()
    mock_manager.delete_chunks = AsyncMock()
    
    # Mock MinIO client
    mock_manager.minio_client = Mock()
    mock_manager.minio_client.insert = Mock()
    mock_manager.minio_client.update = Mock()
    mock_manager.minio_client.delete = Mock()
    mock_manager.minio_client.search = Mock()
    mock_manager.minio_client.get_file = Mock()
    mock_manager.minio_client.get_document_info = Mock()
    mock_manager.minio_client.check_duplicate = Mock()
    mock_manager.minio_client.create_bucket = Mock()
    
    return mock_manager


@pytest.fixture
def sample_session_data():
    """Provide sample session data for testing."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    return {
        "session_id": session_id,
        "user_id": user_id,
        "status": "active",
        "created_at": datetime.utcnow(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat() + 'Z',
        "updated_at": datetime.utcnow(),
        "metadata": {"purpose": "testing"},
        "temp_collection_name": f"temp_{session_id[:8]}"
    }


@pytest.fixture
def sample_document_data():
    """Provide sample document data for testing."""
    document_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    return {
        "document_id": document_id,
        "filename": "test_document.pdf",
        "content_type": "application/pdf",
        "file_size": 1024,
        "upload_timestamp": datetime.utcnow(),
        "session_id": session_id,
        "user_id": user_id,
        "status": "uploaded"
    }


@pytest.fixture
def sample_document_metadata():
    """Provide sample document metadata for testing."""
    document_id = str(uuid.uuid4())
    
    return {
        "document_id": document_id,
        "filename": "test_document.pdf",
        "file_size": 1024,
        "content_type": "application/pdf",
        "file_hash": "abc123def456",
        "chunks_count": 5,
        "processing_status": "processed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "metadata": {"pages": 10, "language": "en"}
    }


@pytest.fixture
def sample_chunks_data():
    """Provide sample chunks data for testing."""
    document_id = str(uuid.uuid4())
    chunks = []
    
    for i in range(3):
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "document_id": document_id,
            "document_title": f"Test Document {i+1}",
            "chunk_text": f"This is test chunk content number {i+1}",
            "vector": [0.1] * 384,  # Sample vector
            "page_number": i + 1,
            "metadata": {"section": f"section_{i+1}"}
        })
    
    return chunks


@pytest.fixture
def sample_upload_file():
    """Create a sample upload file for testing."""
    from fastapi import UploadFile
    
    file_content = b"This is test file content for document upload testing."
    file_obj = io.BytesIO(file_content)
    
    return UploadFile(
        filename="test_document.txt",
        file=file_obj,
        size=len(file_content)
    )


@pytest.fixture
def sample_search_request():
    """Provide sample search request data."""
    return {
        "query_vector": [0.1] * 384,
        "limit": 5,
        "filters": {
            "document_type": "pdf",
            "language": "en"
        }
    }


@pytest.fixture
def mock_successful_response():
    """Provide mock successful database response."""
    return {
        "status": "success",
        "message": "Operation completed successfully"
    }


@pytest.fixture
def mock_error_response():
    """Provide mock error database response."""
    return {
        "status": "error",
        "error": "Database connection failed",
        "message": "Unable to connect to database"
    }


@pytest.fixture
def override_db_manager(mock_db_manager):
    """Override the database manager dependency."""
    def _override():
        return mock_db_manager
    return _override


# Custom pytest markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_db: mark test as requiring database connection"
    )


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    # Set test configuration
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
