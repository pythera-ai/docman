"""
Document management routes for handling document upload, processing, and management.
Implements FR001-FR004 functional requirements.
"""
import uuid
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.config import config
from src.core.models import (
    DocumentMetadata, DocumentPayload, DatabaseOperationResponse
)
from src.api.services.database_manager import DatabaseManager
from src.core.exceptions import DatabaseConnectionException
from src.api.dependencies import get_database_manager


# Document upload model (keeping original)
class Document(BaseModel):
    """Document response model"""
    document_id: str
    filename: str
    content_type: str
    file_size: int
    upload_timestamp: datetime
    session_id: str
    user_id: str
    status: str

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/session/{session_id}/upload", response_model=Document)
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Document:
    """
    FR001: Session Management - Upload document to a specific session.
    FR002: Document Upload and Processing - Handle file upload and processing.
    
    Args:
        session_id: Session identifier
        file: Uploaded file
        metadata: Optional document metadata as JSON string
        db_manager: Database manager instance
        
    Returns:
        Document: Uploaded document information
        
    Raises:
        HTTPException: If upload fails or session is invalid
    """
    try:
        # Generate document ID and user ID
        document_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())  # Random user ID as requested
        
        # Read file content
        file_content = await file.read()
        
        # Generate file hash
        file_hash = hashlib.md5(file_content).hexdigest()
        
        # Create document metadata using the correct model structure
        doc_metadata = DocumentMetadata(
            document_id=document_id,
            filename=file.filename or f"document_{document_id}",
            file_size=len(file_content),
            content_type=file.content_type or "application/octet-stream",
            file_hash=file_hash,
            chunks_count=0,
            processing_status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={
                "session_id": session_id,
                "user_id": user_id,
                "custom_metadata": metadata
            }
        )
        
        # Upload document using database manager with correct parameters
        result = await db_manager.upload_document(
            file_data=file_content,
            filename=doc_metadata.filename,
            content_type=doc_metadata.content_type,
            file_hash=file_hash,
            document_id=document_id,
            metadata=doc_metadata.metadata
        )
        
        # Return document information
        return Document(
            document_id=document_id,
            filename=doc_metadata.filename,
            content_type=doc_metadata.content_type,
            file_size=doc_metadata.file_size,
            upload_timestamp=doc_metadata.created_at or datetime.utcnow(),
            session_id=session_id,
            user_id=user_id,
            status="uploaded"
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/sessions/{session_id}/documents")
async def get_session_documents(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    FR001: Session Management - List all documents in a session.
    
    Args:
        session_id: Session identifier
        limit: Maximum number of documents to return
        offset: Number of documents to skip
        db_manager: Database manager instance
        
    Returns:
        Dict: Documents and pagination info
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        result = await db_manager.get_session_documents(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get session documents: {result['error']}"
            )
        
        return result
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session documents: {str(e)}"
        )

@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> StreamingResponse:
    """
    FR006: Document Management - Download/retrieve original documents.
    
    Args:
        document_id: Document identifier
        db_manager: Database manager instance
        
    Returns:
        StreamingResponse: Document file stream
        
    Raises:
        HTTPException: If document not found or download fails
    """
    try:
        # This is a placeholder implementation
        # In practice, you'd retrieve the document from MinIO and stream it back
        
        raise HTTPException(
            status_code=501,
            detail="Document download not yet implemented"
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download document: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> dict:
    """
    FR006: Document Management - Delete documents.
    
    Args:
        document_id: Document identifier
        db_manager: Database manager instance
        
    Returns:
        dict: Deletion status
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        result = await db_manager.delete_document(document_id=document_id)
        
        return {
            "message": "Document deleted successfully",
            "document_id": document_id,
            "deletion_results": result
        }
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.put("/{document_id}/metadata")
async def update_document_metadata(
    document_id: str,
    metadata: dict,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> dict:
    """
    FR006: Document Management - Update document metadata.
    
    Args:
        document_id: Document identifier
        metadata: New metadata
        db_manager: Database manager instance
        
    Returns:
        dict: Update status
        
    Raises:
        HTTPException: If update fails
    """
    try:
        result = await db_manager.update_document_metadata(
            document_id=document_id,
            updates=metadata
        )
        
        return {
            "message": "Document metadata updated successfully",
            "document_id": document_id,
            "update_result": result
        }
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update document metadata: {str(e)}"
        )


@router.get("/{document_id}/metadata", response_model=DocumentMetadata)
async def get_document_metadata(
    document_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DocumentMetadata:
    """
    FR006: Document Management - Get document metadata.
    
    Args:
        document_id: Document identifier
        db_manager: Database manager instance
        
    Returns:
        DocumentMetadata: Document metadata
        
    Raises:
        HTTPException: If document not found
    """
    try:
        # This is a placeholder implementation
        # In practice, you'd retrieve metadata from the database
        
        raise HTTPException(
            status_code=501,
            detail="Get document metadata not yet implemented"
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document metadata: {str(e)}"
        )
