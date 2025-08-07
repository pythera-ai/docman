"""
Test cases for Session Management API endpoints.
Tests all session-related operations including CRUD operations, user sessions, and administrative functions.
"""
import pytest
import uuid
from unittest.mock import Mock, AsyncMock
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import Dict, Any

from src.api.routes.sessions import router
from src.api.services.database_manager import DatabaseManager
from src.core.models import SessionInfo, SessionCreateRequest, SessionUpdateRequest, AdminStatsResponse
from src.core.exceptions import DatabaseConnectionException


class TestSessionCreation:
    """Test session creation functionality."""

    @pytest.mark.asyncio
    async def test_create_session_success(self, mock_db_manager):
        """Test successful session creation."""
        # Arrange
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        request = SessionCreateRequest(
            user_id=user_id,
            expires_in_hours=24,
            metadata={"purpose": "document_processing"},
            temp_collection_name="temp_collection_001"
        )
        
        # Mock successful database response
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(hours=24)
        
        mock_db_manager.create_session.return_value = {
            "session": {
                "session_id": session_id,
                "user_id": user_id,
                "status": "active",
                "created_at": created_at,
                "expires_at": expires_at,
                "updated_at": created_at,
                "metadata": {"purpose": "document_processing"},
                "temp_collection_name": "temp_collection_001"
            }
        }
        
        from src.api.routes.sessions import create_session
        
        # Act
        result = await create_session(
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, SessionInfo)
        assert result.session_id == session_id
        assert result.user_id == user_id
        assert result.status == "active"
        mock_db_manager.create_session.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_db_manager.create_session.call_args.kwargs
        assert call_args["user_id"] == user_id
        assert call_args["metadata"] == {"purpose": "document_processing"}

    @pytest.mark.asyncio
    async def test_create_session_database_error(self, mock_db_manager):
        """Test session creation with database error."""
        # Arrange
        request = SessionCreateRequest(
            user_id=str(uuid.uuid4()),
            expires_in_hours=12
        )
        
        mock_db_manager.create_session.return_value = {
            "error": "Database connection failed"
        }
        
        from src.api.routes.sessions import create_session
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await create_session(
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to create session" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_database_connection_exception(self, mock_db_manager):
        """Test session creation with database connection exception."""
        # Arrange
        request = SessionCreateRequest(
            user_id=str(uuid.uuid4()),
            expires_in_hours=6
        )
        
        mock_db_manager.create_session.side_effect = DatabaseConnectionException(
            "Cannot connect to database", {"connection": "postgres"}
        )
        
        from src.api.routes.sessions import create_session
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await create_session(
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)


class TestSessionRetrieval:
    """Test session retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_session_success(self, mock_db_manager, sample_session_data):
        """Test successful session retrieval."""
        # Arrange
        session_id = sample_session_data["session_id"]
        mock_db_manager.get_session.return_value = sample_session_data
        
        from src.api.routes.sessions import get_session
        
        # Act
        result = await get_session(
            session_id=session_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, SessionInfo)
        assert result.session_id == session_id
        assert result.user_id == sample_session_data["user_id"]
        mock_db_manager.get_session.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_db_manager):
        """Test session retrieval when session is not found."""
        # Arrange
        session_id = str(uuid.uuid4())
        mock_db_manager.get_session.return_value = None
        
        from src.api.routes.sessions import get_session
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_session(
                session_id=session_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 404
        assert f"Session {session_id} not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_user_sessions_success(self, mock_db_manager):
        """Test successful retrieval of user sessions."""
        # Arrange
        user_id = str(uuid.uuid4())
        
        session_1 = {
            "session_id": str(uuid.uuid4()),
            "user_id": user_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24),
            "updated_at": datetime.utcnow(),
            "metadata": {},
            "temp_collection_name": "temp_001"
        }
        
        session_2 = {
            "session_id": str(uuid.uuid4()),
            "user_id": user_id,
            "status": "expired",
            "created_at": datetime.utcnow() - timedelta(hours=48),
            "expires_at": datetime.utcnow() - timedelta(hours=24),
            "updated_at": datetime.utcnow(),
            "metadata": {},
            "temp_collection_name": "temp_002"
        }
        
        mock_db_manager.get_user_sessions.return_value = {
            "sessions": [session_1, session_2],
            "total_found": 2
        }
        
        from src.api.routes.sessions import get_user_sessions
        
        # Act
        result = await get_user_sessions(
            user_id=user_id,
            status=None,
            limit=50,
            offset=0,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert len(result) == 2
        assert all(isinstance(session, SessionInfo) for session in result)
        assert result[0].session_id == session_1["session_id"]
        assert result[1].session_id == session_2["session_id"]
        mock_db_manager.get_user_sessions.assert_called_once_with(
            user_id=user_id,
            status=None,
            limit=50,
            offset=0
        )

    @pytest.mark.asyncio
    async def test_get_user_sessions_with_status_filter(self, mock_db_manager):
        """Test user sessions retrieval with status filter."""
        # Arrange
        user_id = str(uuid.uuid4())
        
        active_session = {
            "session_id": str(uuid.uuid4()),
            "user_id": user_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=12),
            "updated_at": datetime.utcnow(),
            "metadata": {},
            "temp_collection_name": "temp_active"
        }
        
        mock_db_manager.get_user_sessions.return_value = {
            "sessions": [active_session],
            "total_found": 1
        }
        
        from src.api.routes.sessions import get_user_sessions
        
        # Act
        result = await get_user_sessions(
            user_id=user_id,
            status="active",
            limit=50,
            offset=0,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert len(result) == 1
        assert result[0].status == "active"
        mock_db_manager.get_user_sessions.assert_called_once_with(
            user_id=user_id,
            status="active",
            limit=50,
            offset=0
        )

    @pytest.mark.asyncio
    async def test_get_user_sessions_database_error(self, mock_db_manager):
        """Test user sessions retrieval with database error."""
        # Arrange
        user_id = str(uuid.uuid4())
        
        mock_db_manager.get_user_sessions.return_value = {
            "error": "Database query failed"
        }
        
        from src.api.routes.sessions import get_user_sessions
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_user_sessions(
                user_id=user_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to get user sessions" in str(exc_info.value.detail)


class TestSessionUpdate:
    """Test session update functionality."""

    @pytest.mark.asyncio
    async def test_update_session_success(self, mock_db_manager, sample_session_data):
        """Test successful session update."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        request = SessionUpdateRequest(
            status="paused",
            metadata={"updated_reason": "user_request"},
            temp_collection_name="updated_temp_collection",
            extend_hours=12
        )
        
        # Mock get_session for extend_hours calculation
        mock_db_manager.get_session.return_value = sample_session_data
        
        # Mock update result
        updated_session = {**sample_session_data}
        updated_session["status"] = "paused"
        updated_session["metadata"] = {"updated_reason": "user_request"}
        updated_session["temp_collection_name"] = "updated_temp_collection"
        
        mock_db_manager.update_session.return_value = {
            "session": updated_session
        }
        
        from src.api.routes.sessions import update_session
        
        # Act
        result = await update_session(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, SessionInfo)
        assert result.status == "paused"
        mock_db_manager.update_session.assert_called_once()
        
        # Verify the call included extend hours calculation
        call_args = mock_db_manager.update_session.call_args.kwargs
        assert call_args["session_id"] == session_id
        assert call_args["status"] == "paused"
        assert "expires_at" in call_args  # Extended expiration should be calculated

    @pytest.mark.asyncio
    async def test_update_session_not_found(self, mock_db_manager):
        """Test session update when session is not found."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        request = SessionUpdateRequest(status="paused")
        
        mock_db_manager.update_session.return_value = {
            "error": "Session not found"
        }
        
        from src.api.routes.sessions import update_session
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await update_session(
                session_id=session_id,
                request=request,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 404
        assert "Failed to update session" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_session_extend_hours_calculation(self, mock_db_manager, sample_session_data):
        """Test session update with extend hours calculation."""
        # Arrange
        session_id = sample_session_data["session_id"]
        
        request = SessionUpdateRequest(extend_hours=6)
        
        # Mock current session data
        current_session = sample_session_data.copy()
        current_session["expires_at"] = datetime.utcnow() + timedelta(hours=12)
        mock_db_manager.get_session.return_value = current_session
        
        # Mock successful update
        mock_db_manager.update_session.return_value = {
            "session": current_session
        }
        
        from src.api.routes.sessions import update_session
        
        # Act
        await update_session(
            session_id=session_id,
            request=request,
            db_manager=mock_db_manager
        )
        
        # Assert
        mock_db_manager.get_session.assert_called_once_with(session_id)
        
        # Verify expires_at was extended
        call_args = mock_db_manager.update_session.call_args.kwargs
        assert "expires_at" in call_args
        # The extended time should be original + 6 hours
        extended_time = call_args["expires_at"]
        assert extended_time > current_session["expires_at"]


class TestSessionDeletion:
    """Test session deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, mock_db_manager):
        """Test successful session deletion."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        mock_db_manager.delete_session.return_value = {
            "deleted": True,
            "cleanup_results": {
                "documents_removed": 3,
                "chunks_removed": 15
            }
        }
        
        from src.api.routes.sessions import delete_session
        
        # Act
        result = await delete_session(
            session_id=session_id,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["message"] == "Session deleted successfully"
        assert result["session_id"] == session_id
        assert result["deleted"] is True
        mock_db_manager.delete_session.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, mock_db_manager):
        """Test session deletion when session is not found."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        mock_db_manager.delete_session.return_value = {
            "error": "Session not found"
        }
        
        from src.api.routes.sessions import delete_session
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_session(
                session_id=session_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 404
        assert "Failed to delete session" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_session_database_connection_error(self, mock_db_manager):
        """Test session deletion with database connection error."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        mock_db_manager.delete_session.side_effect = DatabaseConnectionException(
            "Connection lost", {"database": "postgres"}
        )
        
        from src.api.routes.sessions import delete_session
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_session(
                session_id=session_id,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)


class TestSessionExpiration:
    """Test session expiration functionality."""

    @pytest.mark.asyncio
    async def test_expire_old_sessions_success(self, mock_db_manager):
        """Test successful expiration of old sessions."""
        # Arrange
        mock_db_manager.expire_old_sessions.return_value = {
            "expired_count": 5,
            "processing_time_ms": 150
        }
        
        from src.api.routes.sessions import expire_old_sessions
        
        # Act
        result = await expire_old_sessions(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["message"] == "Session expiration completed"
        assert result["expired_count"] == 5
        assert result["processing_time_ms"] == 150
        mock_db_manager.expire_old_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_expire_old_sessions_database_error(self, mock_db_manager):
        """Test session expiration with database error."""
        # Arrange
        mock_db_manager.expire_old_sessions.return_value = {
            "error": "Failed to update expired sessions"
        }
        
        from src.api.routes.sessions import expire_old_sessions
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await expire_old_sessions(
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to expire sessions" in str(exc_info.value.detail)


class TestSessionDocuments:
    """Test session document operations."""

    @pytest.mark.asyncio
    async def test_get_session_documents_success(self, mock_db_manager):
        """Test successful retrieval of session documents."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        mock_db_manager.get_session_documents.return_value = {
            "documents": [
                {
                    "document_id": str(uuid.uuid4()),
                    "filename": "doc1.pdf",
                    "file_size": 1024,
                    "upload_time": datetime.utcnow().isoformat()
                },
                {
                    "document_id": str(uuid.uuid4()),
                    "filename": "doc2.txt",
                    "file_size": 512,
                    "upload_time": datetime.utcnow().isoformat()
                }
            ],
            "total_found": 2,
            "offset": 0,
            "limit": 100
        }
        
        from src.api.routes.sessions import get_session_documents
        
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
        assert result["documents"][0]["filename"] == "doc1.pdf"
        mock_db_manager.get_session_documents.assert_called_once_with(
            session_id=session_id,
            limit=100,
            offset=0
        )

    @pytest.mark.asyncio
    async def test_get_session_documents_with_pagination(self, mock_db_manager):
        """Test session documents retrieval with pagination."""
        # Arrange
        session_id = str(uuid.uuid4())
        
        mock_db_manager.get_session_documents.return_value = {
            "documents": [{"document_id": str(uuid.uuid4()), "filename": f"doc{i}.pdf"} for i in range(10)],
            "total_found": 50,
            "offset": 20,
            "limit": 10
        }
        
        from src.api.routes.sessions import get_session_documents
        
        # Act
        result = await get_session_documents(
            session_id=session_id,
            limit=10,
            offset=20,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["total_found"] == 50
        assert len(result["documents"]) == 10
        assert result["offset"] == 20
        assert result["limit"] == 10


class TestAdminOperations:
    """Test administrative operations."""

    @pytest.mark.asyncio
    async def test_get_admin_stats_success(self, mock_db_manager):
        """Test successful retrieval of admin statistics."""
        # Arrange
        # Mock database health
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        # Mock session statistics
        all_sessions = {"sessions": [{}] * 10, "total_found": 10}
        active_sessions = {"sessions": [{}] * 7, "total_found": 7}
        
        mock_db_manager.get_user_sessions.side_effect = [all_sessions, active_sessions]
        
        from src.api.routes.sessions import get_admin_stats
        
        # Act
        result = await get_admin_stats(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, AdminStatsResponse)
        assert result.total_sessions == 10
        assert result.active_sessions == 7
        assert result.database_status["overall"] is True
        mock_db_manager.is_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_admin_stats_database_error(self, mock_db_manager):
        """Test admin stats with database connection error."""
        # Arrange
        mock_db_manager.is_healthy.side_effect = DatabaseConnectionException(
            "Cannot connect to stats database", {}
        )
        
        from src.api.routes.sessions import get_admin_stats
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_admin_stats(
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 503
        assert "Database connection error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_perform_system_cleanup_dry_run(self, mock_db_manager):
        """Test system cleanup dry run."""
        # Arrange
        mock_db_manager.expire_old_sessions.return_value = {
            "expired_count": 3
        }
        
        from src.api.routes.sessions import perform_system_cleanup
        
        # Act
        result = await perform_system_cleanup(
            cleanup_type="normal",
            dry_run=True,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["cleanup_type"] == "normal"
        assert result["dry_run"] is True
        assert "Dry run" in result["message"]
        # Should not call expire_old_sessions in dry run
        mock_db_manager.expire_old_sessions.assert_not_called()

    @pytest.mark.asyncio
    async def test_perform_system_cleanup_actual(self, mock_db_manager):
        """Test actual system cleanup."""
        # Arrange
        mock_db_manager.expire_old_sessions.return_value = {
            "expired_count": 5
        }
        
        from src.api.routes.sessions import perform_system_cleanup
        
        # Act
        result = await perform_system_cleanup(
            cleanup_type="normal",
            dry_run=False,
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["cleanup_type"] == "normal"
        assert result["dry_run"] is False
        assert "Actual" in result["message"]
        assert result["results"]["expired_sessions_cleaned"] == 5
        mock_db_manager.expire_old_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_system_cleanup_invalid_type(self, mock_db_manager):
        """Test system cleanup with invalid cleanup type."""
        # Arrange
        from src.api.routes.sessions import perform_system_cleanup
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await perform_system_cleanup(
                cleanup_type="invalid",
                dry_run=False,
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid cleanup type" in str(exc_info.value.detail)


@pytest.mark.integration
class TestSessionsIntegration:
    """Integration tests for session management workflow."""

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, mock_db_manager):
        """Test complete session lifecycle: create -> get -> update -> expire -> delete."""
        # Import functions
        from src.api.routes.sessions import (
            create_session, get_session, update_session, 
            expire_old_sessions, delete_session
        )
        
        # Setup
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        # Mock responses for each operation
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(hours=24)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "active",
            "created_at": created_at,
            "expires_at": expires_at,
            "updated_at": created_at,
            "metadata": {"purpose": "testing"},
            "temp_collection_name": "temp_test"
        }
        
        # 1. Create session
        mock_db_manager.create_session.return_value = {"session": session_data}
        
        create_request = SessionCreateRequest(
            user_id=user_id,
            expires_in_hours=24,
            metadata={"purpose": "testing"}
        )
        
        created_session = await create_session(
            request=create_request,
            db_manager=mock_db_manager
        )
        
        assert created_session.user_id == user_id
        
        # 2. Get session
        mock_db_manager.get_session.return_value = session_data
        
        retrieved_session = await get_session(
            session_id=session_id,
            db_manager=mock_db_manager
        )
        
        assert retrieved_session.session_id == session_id
        
        # 3. Update session
        updated_session_data = {**session_data}
        updated_session_data["status"] = "paused"
        mock_db_manager.update_session.return_value = {"session": updated_session_data}
        
        update_request = SessionUpdateRequest(status="paused")
        
        updated_session = await update_session(
            session_id=session_id,
            request=update_request,
            db_manager=mock_db_manager
        )
        
        assert updated_session.status == "paused"
        
        # 4. Expire old sessions
        mock_db_manager.expire_old_sessions.return_value = {"expired_count": 1}
        
        expire_result = await expire_old_sessions(db_manager=mock_db_manager)
        
        assert expire_result["expired_count"] == 1
        
        # 5. Delete session
        mock_db_manager.delete_session.return_value = {"deleted": True}
        
        delete_result = await delete_session(
            session_id=session_id,
            db_manager=mock_db_manager
        )
        
        assert delete_result["deleted"] is True
        
        # Verify all operations were called
        mock_db_manager.create_session.assert_called_once()
        mock_db_manager.get_session.assert_called()
        mock_db_manager.update_session.assert_called_once()
        mock_db_manager.expire_old_sessions.assert_called_once()
        mock_db_manager.delete_session.assert_called_once()
