"""
Integration tests for the complete Document Management System API.
Tests end-to-end workflows combining all API services.
"""
import pytest
import uuid
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timedelta
from typing import Dict, Any
import io

from src.api.main import app
from src.api.services.database_manager import DatabaseManager


@pytest.mark.integration 
class TestCompleteWorkflow:
    """Test complete document management workflow."""

    @pytest.fixture
    async def setup_workflow(self, mock_db_manager):
        """Setup a complete workflow environment."""
        # Mock all database operations for workflow
        
        # Session operations
        session_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24),
            "updated_at": datetime.utcnow(),
            "metadata": {"workflow": "test"},
            "temp_collection_name": f"temp_{session_id[:8]}"
        }
        
        mock_db_manager.create_session.return_value = {"session": session_data}
        mock_db_manager.get_session.return_value = session_data
        mock_db_manager.update_session.return_value = {"session": session_data}
        mock_db_manager.delete_session.return_value = {"deleted": True}
        
        # Document operations
        document_id = str(uuid.uuid4())
        document_data = {
            "document_id": document_id,
            "filename": "workflow_test.pdf",
            "file_size": 1024,
            "content_type": "application/pdf",
            "file_hash": "workflow_hash",
            "chunks_count": 3,
            "processing_status": "processed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {"session_id": session_id}
        }
        
        mock_db_manager.create_document.return_value = {
            "status": "success",
            "document_id": document_id
        }
        mock_db_manager.get_document.return_value = document_data
        mock_db_manager.download_document.return_value = {
            "file_content": b"Test workflow document content",
            "filename": "workflow_test.pdf",
            "content_type": "application/pdf"
        }
        mock_db_manager.delete_document.return_value = {"status": "success"}
        
        # Chunks operations
        chunk_ids = [str(uuid.uuid4()) for _ in range(3)]
        search_results = [
            {
                "id": chunk_id,
                "score": 0.9 - i * 0.1,
                "payload": {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "doc_title": "workflow_test.pdf",
                    "chunk_content": f"Workflow chunk content {i+1}",
                    "page": i + 1
                }
            }
            for i, chunk_id in enumerate(chunk_ids)
        ]
        
        mock_db_manager.create_chunks.return_value = {
            "status": "success",
            "points_processed": 3
        }
        mock_db_manager.get_chunks.return_value = {
            "chunks": search_results,
            "total_found": 3
        }
        mock_db_manager.update_chunks.return_value = {
            "status": "success",
            "points_updated": 3
        }
        mock_db_manager.delete_chunks.return_value = {"status": "success"}
        
        # Health check
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "document_id": document_id,
            "chunk_ids": chunk_ids,
            "session_data": session_data,
            "document_data": document_data
        }

    @pytest.mark.asyncio
    async def test_complete_document_processing_workflow(self, mock_db_manager, setup_workflow):
        """Test complete workflow: create session -> upload document -> process chunks -> search -> cleanup."""
        
        # Import all needed functions
        from src.api.routes.sessions import create_session, get_session, delete_session
        from src.api.routes.documents import upload_document, get_document_metadata
        from src.api.routes.chunks import upload_chunks, search_chunks, delete_chunks
        from src.api.routes.health import health_check
        from src.core.models import SessionCreateRequest
        
        workflow_data = await setup_workflow
        
        # Step 1: Health check - verify system is ready
        health = await health_check()
        assert health.status == "healthy"
        
        # Step 2: Create session for document processing
        session_request = SessionCreateRequest(
            user_id=workflow_data["user_id"],
            expires_in_hours=24,
            metadata={"purpose": "document_processing", "workflow": "test"}
        )
        
        session = await create_session(
            request=session_request,
            db_manager=mock_db_manager
        )
        
        assert session.session_id == workflow_data["session_id"]
        assert session.status == "active"
        
        # Step 3: Upload document to session
        file_content = b"Test document content for workflow processing"
        file_obj = io.BytesIO(file_content)
        upload_file = Mock()
        upload_file.filename = "workflow_test.pdf"
        upload_file.read = AsyncMock(return_value=file_content)
        upload_file.content_type = "application/pdf"
        
        document = await upload_document(
            session_id=workflow_data["session_id"],
            file=upload_file,
            metadata=json.dumps({"workflow": "test", "priority": "high"}),
            db_manager=mock_db_manager
        )
        
        assert document.document_id is not None
        assert document.filename == "workflow_test.pdf"
        assert document.session_id == workflow_data["session_id"]
        
        # Step 4: Process and upload chunks for the document
        chunks_data = []
        for i in range(3):
            chunk = Mock()
            chunk.vector = [0.1 + i * 0.1] * 384
            chunk.document_id = workflow_data["document_id"]
            chunk.document_title = "workflow_test.pdf"
            chunk.chunk_text = f"Workflow chunk content {i+1}"
            chunk.page_number = i + 1
            chunk.metadata = {"workflow": "test", "chunk_index": i}
            chunks_data.append(chunk)
        
        upload_request = Mock()
        upload_request.chunks = chunks_data
        
        chunk_upload_result = await upload_chunks(
            session_id=workflow_data["session_id"],
            request=upload_request,
            db_manager=mock_db_manager
        )
        
        assert chunk_upload_result.status == "success"
        assert chunk_upload_result.chunks_processed == 3
        
        # Step 5: Search chunks to verify processing
        search_request = Mock()
        search_request.query_vector = [0.2] * 384
        search_request.limit = 5
        search_request.filters = {"document_id": workflow_data["document_id"]}
        
        search_results = await search_chunks(
            session_id=workflow_data["session_id"],
            request=search_request,
            db_manager=mock_db_manager
        )
        
        assert len(search_results.results) == 3
        assert search_results.total_results == 3
        assert all(result.document_id == workflow_data["document_id"] for result in search_results.results)
        
        # Step 6: Verify document metadata
        doc_metadata = await get_document_metadata(
            document_id=workflow_data["document_id"],
            db_manager=mock_db_manager
        )
        
        assert doc_metadata.document_id == workflow_data["document_id"]
        assert doc_metadata.filename == "workflow_test.pdf"
        
        # Step 7: Cleanup - delete chunks and session
        delete_chunks_request = Mock()
        delete_chunks_request.chunk_ids = workflow_data["chunk_ids"]
        
        chunks_delete_result = await delete_chunks(
            session_id=workflow_data["session_id"],
            request=delete_chunks_request,
            db_manager=mock_db_manager
        )
        
        assert chunks_delete_result.status == "success"
        
        # Step 8: Delete session
        session_delete_result = await delete_session(
            session_id=workflow_data["session_id"],
            db_manager=mock_db_manager
        )
        
        assert session_delete_result["deleted"] is True
        
        # Verify all database operations were called
        mock_db_manager.create_session.assert_called_once()
        mock_db_manager.create_document.assert_called_once()
        mock_db_manager.create_chunks.assert_called_once()
        mock_db_manager.get_chunks.assert_called_once()
        mock_db_manager.delete_chunks.assert_called_once()
        mock_db_manager.delete_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_session_document_sharing_workflow(self, mock_db_manager):
        """Test workflow with multiple sessions accessing shared documents."""
        
        from src.api.routes.sessions import create_session
        from src.api.routes.documents import upload_document, list_documents
        from src.api.routes.chunks import search_chunks
        from src.core.models import SessionCreateRequest
        
        # Setup multiple sessions
        user_id = str(uuid.uuid4())
        session_ids = [str(uuid.uuid4()) for _ in range(2)]
        
        # Mock session creation for multiple sessions
        def create_session_side_effect(*args, **kwargs):
            session_id = session_ids.pop(0) if session_ids else str(uuid.uuid4())
            return {
                "session": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(hours=12),
                    "updated_at": datetime.utcnow(),
                    "metadata": {"purpose": "multi_session_test"},
                    "temp_collection_name": f"temp_{session_id[:8]}"
                }
            }
        
        mock_db_manager.create_session.side_effect = create_session_side_effect
        
        # Mock document operations
        shared_document_id = str(uuid.uuid4())
        mock_db_manager.create_document.return_value = {
            "status": "success",
            "document_id": shared_document_id
        }
        
        # Mock search results for both sessions
        search_results = [
            {
                "id": str(uuid.uuid4()),
                "score": 0.95,
                "payload": {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": shared_document_id,
                    "doc_title": "shared_document.pdf",
                    "chunk_content": "Shared content accessible by multiple sessions",
                    "page": 1
                }
            }
        ]
        
        mock_db_manager.get_chunks.return_value = {
            "chunks": search_results,
            "total_found": 1
        }
        
        # Mock document listing
        mock_db_manager.minio_client = Mock()
        mock_db_manager.minio_client.search.return_value = {
            "documents": [
                {
                    "document_id": shared_document_id,
                    "filename": "shared_document.pdf",
                    "file_size": 2048,
                    "upload_time": datetime.utcnow().isoformat()
                }
            ],
            "processing_time_ms": 50
        }
        
        # Create first session
        session1_request = SessionCreateRequest(
            user_id=user_id,
            expires_in_hours=12,
            metadata={"role": "primary", "access": "write"}
        )
        
        session1 = await create_session(
            request=session1_request,
            db_manager=mock_db_manager
        )
        
        # Create second session
        session2_request = SessionCreateRequest(
            user_id=user_id,
            expires_in_hours=12,
            metadata={"role": "secondary", "access": "read"}
        )
        
        session2 = await create_session(
            request=session2_request,
            db_manager=mock_db_manager
        )
        
        # Upload document in first session
        file_obj = io.BytesIO(b"Shared document content")
        upload_file = Mock()
        upload_file.filename = "shared_document.pdf"
        upload_file.read = AsyncMock(return_value=b"Shared document content")
        upload_file.content_type = "application/pdf"
        
        document = await upload_document(
            session_id=session1.session_id,
            file=upload_file,
            metadata=json.dumps({"shared": True, "owner": session1.session_id}),
            db_manager=mock_db_manager
        )
        
        assert document.session_id == session1.session_id
        
        # Search from both sessions should find the shared document
        search_request = Mock()
        search_request.query_vector = [0.3] * 384
        search_request.limit = 10
        search_request.filters = {"shared": True}
        
        # Search from session 1
        search_results_1 = await search_chunks(
            session_id=session1.session_id,
            request=search_request,
            db_manager=mock_db_manager
        )
        
        # Search from session 2
        search_results_2 = await search_chunks(
            session_id=session2.session_id,
            request=search_request,
            db_manager=mock_db_manager
        )
        
        # Both sessions should find the document
        assert len(search_results_1.results) == 1
        assert len(search_results_2.results) == 1
        assert search_results_1.results[0].document_id == shared_document_id
        assert search_results_2.results[0].document_id == shared_document_id
        
        # List documents should show shared document
        documents_list = await list_documents(
            db_manager=mock_db_manager
        )
        
        assert len(documents_list["documents"]) == 1
        assert documents_list["documents"][0]["document_id"] == shared_document_id
        
        # Verify database calls
        assert mock_db_manager.create_session.call_count == 2
        assert mock_db_manager.create_document.call_count == 1
        assert mock_db_manager.get_chunks.call_count == 2  # Two search calls

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, mock_db_manager):
        """Test workflow with various error conditions and recovery."""
        
        from src.api.routes.sessions import create_session, get_session
        from src.api.routes.documents import upload_document
        from src.api.routes.chunks import upload_chunks
        from src.api.routes.health import detailed_health_check
        from src.core.models import SessionCreateRequest
        from src.core.exceptions import DatabaseConnectionException
        
        # Step 1: Start with unhealthy system
        mock_db_manager.is_healthy.return_value = {
            "overall": False,
            "minio": False,  # MinIO is down
            "qdrant": True,
            "postgres": True
        }
        
        # Health check should show system issues
        health = await detailed_health_check(db_manager=mock_db_manager)
        assert health.status == "unhealthy"
        assert health.databases.minio is False
        
        # Step 2: Try to create session - should succeed (only needs Postgres)
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": str(uuid.uuid4()),
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=12),
            "updated_at": datetime.utcnow(),
            "metadata": {"error_test": True},
            "temp_collection_name": f"temp_{session_id[:8]}"
        }
        
        mock_db_manager.create_session.return_value = {"session": session_data}
        
        session_request = SessionCreateRequest(
            user_id=session_data["user_id"],
            expires_in_hours=12,
            metadata={"error_handling": "test"}
        )
        
        session = await create_session(
            request=session_request,
            db_manager=mock_db_manager
        )
        
        assert session.session_id == session_id
        
        # Step 3: Try to upload document - should fail due to MinIO being down
        mock_db_manager.create_document.side_effect = DatabaseConnectionException(
            "MinIO connection failed", {"service": "minio"}
        )
        
        file_obj = io.BytesIO(b"Test content")
        upload_file = Mock()
        upload_file.filename = "error_test.txt"
        upload_file.read = AsyncMock(return_value=b"Test content")
        upload_file.content_type = "text/plain"
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await upload_document(
                session_id=session_id,
                file=upload_file,
                metadata=None,
                db_manager=mock_db_manager
            )
        
        # Step 4: System recovery - MinIO comes back online
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,   # MinIO is back
            "qdrant": True,
            "postgres": True
        }
        
        # Remove the side effect for document creation
        mock_db_manager.create_document.side_effect = None
        mock_db_manager.create_document.return_value = {
            "status": "success",
            "document_id": str(uuid.uuid4())
        }
        
        # Health check should now show healthy
        health_recovered = await detailed_health_check(db_manager=mock_db_manager)
        assert health_recovered.status == "healthy"
        assert health_recovered.databases.minio is True
        
        # Step 5: Retry document upload - should succeed now
        document = await upload_document(
            session_id=session_id,
            file=upload_file,
            metadata=json.dumps({"retry": True}),
            db_manager=mock_db_manager
        )
        
        assert document.filename == "error_test.txt"
        assert document.session_id == session_id
        
        # Step 6: Try chunk operations - simulate Qdrant issues
        mock_db_manager.create_chunks.side_effect = DatabaseConnectionException(
            "Qdrant temporarily unavailable", {"service": "qdrant"}
        )
        
        chunk = Mock()
        chunk.vector = [0.5] * 384
        chunk.document_id = document.document_id
        chunk.document_title = "error_test.txt"
        chunk.chunk_text = "Error handling test chunk"
        chunk.page_number = 1
        chunk.metadata = {"test": "error_handling"}
        
        upload_request = Mock()
        upload_request.chunks = [chunk]
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await upload_chunks(
                session_id=session_id,
                request=upload_request,
                db_manager=mock_db_manager
            )
        
        # Verify that sessions can still be accessed even with chunk service issues
        mock_db_manager.get_session.return_value = session_data
        
        retrieved_session = await get_session(
            session_id=session_id,
            db_manager=mock_db_manager
        )
        
        assert retrieved_session.session_id == session_id
        
        # Verify error handling calls were made
        assert mock_db_manager.create_session.call_count == 1
        assert mock_db_manager.create_document.call_count == 1
        assert mock_db_manager.create_chunks.call_count == 1
        assert mock_db_manager.get_session.call_count == 1


@pytest.mark.integration
class TestPerformanceWorkflow:
    """Test system performance under various load conditions."""

    @pytest.mark.asyncio
    async def test_bulk_operations_workflow(self, mock_db_manager):
        """Test workflow with bulk operations to verify system handles load."""
        
        from src.api.routes.sessions import create_session
        from src.api.routes.documents import upload_document
        from src.api.routes.chunks import upload_chunks, search_chunks
        from src.core.models import SessionCreateRequest
        
        # Setup bulk operation responses
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=6),
            "updated_at": datetime.utcnow(),
            "metadata": {"bulk_test": True},
            "temp_collection_name": f"temp_bulk_{session_id[:8]}"
        }
        
        mock_db_manager.create_session.return_value = {"session": session_data}
        
        # Create session for bulk operations
        session_request = SessionCreateRequest(
            user_id=user_id,
            expires_in_hours=6,
            metadata={"purpose": "bulk_operations", "batch_size": 100}
        )
        
        session = await create_session(
            request=session_request,
            db_manager=mock_db_manager
        )
        
        # Simulate bulk document uploads
        document_ids = []
        for i in range(10):  # Upload 10 documents
            document_id = str(uuid.uuid4())
            document_ids.append(document_id)
            
            mock_db_manager.create_document.return_value = {
                "status": "success",
                "document_id": document_id
            }
            
            file_content = f"Bulk document content {i+1}".encode()
            file_obj = io.BytesIO(file_content)
            upload_file = Mock()
            upload_file.filename = f"bulk_doc_{i+1}.txt"
            upload_file.read = AsyncMock(return_value=file_content)
            upload_file.content_type = "text/plain"
            
            document = await upload_document(
                session_id=session_id,
                file=upload_file,
                metadata=json.dumps({"batch": i+1, "bulk": True}),
                db_manager=mock_db_manager
            )
            
            assert document.filename == f"bulk_doc_{i+1}.txt"
        
        # Simulate bulk chunk processing
        bulk_chunks = []
        for i, doc_id in enumerate(document_ids):
            for j in range(5):  # 5 chunks per document
                chunk = Mock()
                chunk.vector = [0.1 + i * 0.01 + j * 0.001] * 384
                chunk.document_id = doc_id
                chunk.document_title = f"bulk_doc_{i+1}.txt"
                chunk.chunk_text = f"Bulk chunk {j+1} for document {i+1}"
                chunk.page_number = j + 1
                chunk.metadata = {"doc_index": i, "chunk_index": j, "bulk": True}
                bulk_chunks.append(chunk)
        
        # Mock successful bulk chunk upload
        mock_db_manager.create_chunks.return_value = {
            "status": "success",
            "points_processed": len(bulk_chunks),
            "failed_points": None
        }
        
        upload_request = Mock()
        upload_request.chunks = bulk_chunks
        
        chunk_result = await upload_chunks(
            session_id=session_id,
            request=upload_request,
            db_manager=mock_db_manager
        )
        
        assert chunk_result.status == "success"
        assert chunk_result.chunks_processed == len(bulk_chunks)  # 50 chunks total
        
        # Simulate bulk search operations
        search_queries = [
            [0.2 + i * 0.05] * 384 for i in range(5)  # 5 different search queries
        ]
        
        for i, query_vector in enumerate(search_queries):
            # Mock search results for each query
            mock_search_results = [
                {
                    "id": str(uuid.uuid4()),
                    "score": 0.9 - j * 0.1,
                    "payload": {
                        "chunk_id": str(uuid.uuid4()),
                        "document_id": document_ids[j % len(document_ids)],
                        "doc_title": f"bulk_doc_{(j % len(document_ids)) + 1}.txt",
                        "chunk_content": f"Search result {j+1} for query {i+1}",
                        "page": 1
                    }
                }
                for j in range(3)  # 3 results per query
            ]
            
            mock_db_manager.get_chunks.return_value = {
                "chunks": mock_search_results,
                "total_found": len(mock_search_results)
            }
            
            search_request = Mock()
            search_request.query_vector = query_vector
            search_request.limit = 10
            search_request.filters = {"bulk": True}
            
            search_results = await search_chunks(
                session_id=session_id,
                request=search_request,
                db_manager=mock_db_manager
            )
            
            assert len(search_results.results) == 3
            assert search_results.total_results == 3
        
        # Verify all operations completed successfully
        assert mock_db_manager.create_session.call_count == 1
        assert mock_db_manager.create_document.call_count == 10
        assert mock_db_manager.create_chunks.call_count == 1
        assert mock_db_manager.get_chunks.call_count == 5  # 5 search queries

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_operations_workflow(self, mock_db_manager):
        """Test workflow with concurrent operations to verify thread safety."""
        
        import asyncio
        from src.api.routes.sessions import create_session, get_session
        from src.core.models import SessionCreateRequest
        
        # Setup concurrent session operations
        user_ids = [str(uuid.uuid4()) for _ in range(5)]
        session_ids = [str(uuid.uuid4()) for _ in range(5)]
        
        def create_session_side_effect(*args, **kwargs):
            # Return different session data based on call
            call_count = mock_db_manager.create_session.call_count - 1
            if call_count < len(session_ids):
                return {
                    "session": {
                        "session_id": session_ids[call_count],
                        "user_id": user_ids[call_count],
                        "status": "active",
                        "created_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(hours=1),
                        "updated_at": datetime.utcnow(),
                        "metadata": {"concurrent": True, "index": call_count},
                        "temp_collection_name": f"temp_concurrent_{call_count}"
                    }
                }
            return {"session": {"session_id": str(uuid.uuid4())}}
        
        mock_db_manager.create_session.side_effect = create_session_side_effect
        
        def get_session_side_effect(session_id):
            # Return session data for the requested session
            try:
                index = session_ids.index(session_id)
                return {
                    "session_id": session_id,
                    "user_id": user_ids[index],
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(hours=1),
                    "updated_at": datetime.utcnow(),
                    "metadata": {"concurrent": True, "index": index},
                    "temp_collection_name": f"temp_concurrent_{index}"
                }
            except ValueError:
                return None
        
        mock_db_manager.get_session.side_effect = get_session_side_effect
        
        # Create multiple sessions concurrently
        async def create_concurrent_session(index):
            session_request = SessionCreateRequest(
                user_id=user_ids[index],
                expires_in_hours=1,
                metadata={"concurrent": True, "index": index}
            )
            
            return await create_session(
                request=session_request,
                db_manager=mock_db_manager
            )
        
        # Execute concurrent session creation
        session_tasks = [
            create_concurrent_session(i) for i in range(5)
        ]
        
        created_sessions = await asyncio.gather(*session_tasks)
        
        # Verify all sessions were created successfully
        assert len(created_sessions) == 5
        for i, session in enumerate(created_sessions):
            assert session.user_id == user_ids[i]
            assert session.session_id in session_ids
        
        # Perform concurrent session retrievals
        async def get_concurrent_session(session_id):
            return await get_session(
                session_id=session_id,
                db_manager=mock_db_manager
            )
        
        retrieval_tasks = [
            get_concurrent_session(session_id) for session_id in session_ids
        ]
        
        retrieved_sessions = await asyncio.gather(*retrieval_tasks)
        
        # Verify all sessions were retrieved successfully
        assert len(retrieved_sessions) == 5
        for session in retrieved_sessions:
            assert session.session_id in session_ids
            assert session.user_id in user_ids
        
        # Verify database was called the expected number of times
        assert mock_db_manager.create_session.call_count == 5
        assert mock_db_manager.get_session.call_count == 5
