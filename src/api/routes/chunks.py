"""
Chunks management routes - CRUD operations for document chunks.
Supports the 4 core features:
1. Session management integration
2. Document management integration
3. Chunks CRUD operations
4. Metrics and logging
"""
from typing import List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from src.core.config import config
from src.core.models import (
    ChunkUpdateRequest, ChunkDeleteRequest, ChunkUploadRequest, ChunkUploadResponse,
    ChunkOperationResponse, SearchRequest, SearchResponse, SearchResult
)
from src.api.services.database_manager import DatabaseManager
from src.core.exceptions import DatabaseConnectionException
from src.api.dependencies import get_database_manager


router = APIRouter(prefix="/chunks", tags=["chunks"])


@router.post("/session/{session_id}/chunks", response_model=ChunkUploadResponse)
async def upload_chunks(
    session_id: str,
    request: ChunkUploadRequest,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> ChunkUploadResponse:
    """
    Upload chunks to Qdrant vector database (Core Feature: Chunks CRUD + Session integration).
    
    Args:
        session_id: Session identifier
        request: Chunk upload request containing list of chunks
        db_manager: Database manager instance
        
    Returns:
        ChunkUploadResponse: Upload result with processing details
        
    Raises:
        HTTPException: If upload fails
    """
    try:
        start_time = datetime.utcnow()
        
        # Prepare chunks for database manager
        chunks_data = []
        for chunk in request.chunks:
            chunk_data = {
                "vector": chunk.vector,
                "payload": {
                    "document_id": chunk.document_id,
                    "doc_title": chunk.document_title,
                    "page": chunk.page_number or 0,
                    "chunk_content": chunk.chunk_text,
                    "file_url": f"session/{session_id}/document/{chunk.document_id}",
                    "user_id": None,  # Will be set by session context
                    "session_id": session_id,
                    **(chunk.metadata or {})
                },
            }
            chunks_data.append(chunk_data)
        
        # Store chunks using database manager
        result = await db_manager.create_chunks(chunks=chunks_data)
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        if result.get("status") == "success":
            return ChunkUploadResponse(
                status="success",
                chunks_processed=result.get("points_processed", 0),
                processing_time_ms=processing_time,
                failed_chunks=result.get("failed_points")
            )
        else:
            return ChunkUploadResponse(
                status="partial_failure",
                chunks_processed=result.get("points_processed", 0),
                processing_time_ms=processing_time,
                failed_chunks=result.get("failed_points", [{"error": result.get("message", "Unknown error")}])
            )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload chunks: {str(e)}"
        )


@router.post("/session/{session_id}/search", response_model=SearchResponse)
async def search_chunks(
    session_id: str,
    request: SearchRequest,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> SearchResponse:
    """
    Search chunks using vector similarity.
    
    Args:
        session_id: Session identifier
        request: Search request with query vector and filters
        db_manager: Database manager instance
        
    Returns:
        SearchResponse: Search results with chunks
        
    Raises:
        HTTPException: If search fails
    """
    try:
        start_time = datetime.utcnow()
        
        # Prepare search parameters
        search_params = {
            "query_vector": request.query_vector,
            "limit": request.limit,
            "session_id": session_id,
            **(request.filters or {})
        }
        
        # Perform search using database manager
        result = await db_manager.get_chunks(
            query_vector=request.query_vector,
            filters=search_params,
            limit=request.limit or 5
        )
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Format results according to your specified structure
        search_results = []
        for chunk in result.get("chunks", []):
            payload = chunk.get("payload", {})
            search_results.append(SearchResult(
                chunk_id=payload.get("chunk_id", str(chunk.get("id", ""))),
                document_id=payload.get("document_id", ""),
                document_title=payload.get("doc_title", ""),
                chunk_text=payload.get("chunk_content", ""),
                similarity_score=chunk.get("score", 0.0),
                source="temp" if session_id else "main",  # Determine source based on session
                metadata={
                    "page_number": payload.get("page", 0),
                    "section": payload.get("section", ""),
                    **{k: v for k, v in payload.items() if k not in ["document_id", "doc_title", "chunk_content", "page", "section"]}
                }
            ))
        
        return SearchResponse(
            query_vector=request.query_vector,
            results=search_results,
            total_results=result.get("total_found", len(search_results)),
            search_time_ms=processing_time
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.put("/session/{session_id}/chunks", response_model=ChunkOperationResponse)
async def update_chunks(
    session_id: str,
    updates: List[ChunkUpdateRequest],
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> ChunkOperationResponse:
    """
    Update chunks in Qdrant vector database.
    
    Args:
        session_id: Session identifier
        updates: List of chunk update requests
        db_manager: Database manager instance
        
    Returns:
        ChunkOperationResponse: Update operation result
        
    Raises:
        HTTPException: If update fails
    """
    try:
        start_time = datetime.utcnow()
        
        # Prepare update data
        update_points = []
        for update in updates:
            point_data: Dict[str, Any] = {
                "id": update.chunk_id
            }
            
            # Add vector if provided
            if update.vector:
                point_data["vector"] = update.vector
            
            # Prepare payload updates
            payload_updates = {}
            if update.chunk_text:
                payload_updates["chunk_content"] = update.chunk_text
            if update.metadata:
                payload_updates.update(update.metadata)
            
            # Add session context
            payload_updates["session_id"] = session_id
            payload_updates["updated_at"] = datetime.utcnow().isoformat()
            
            if payload_updates:
                point_data["payload"] = payload_updates
            
            update_points.append(point_data)
        
        # Perform update using database manager
        result = await db_manager.update_chunks(
            chunks=update_points
        )
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return ChunkOperationResponse(
            status="success" if result.get("status") == "success" else "partial_failure",
            chunks_affected=result.get("points_updated", 0),
            processing_time_ms=processing_time,
            errors=result.get("failed_updates")
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update chunks: {str(e)}"
        )


@router.delete("/session/{session_id}/chunks", response_model=ChunkOperationResponse)
async def delete_chunks(
    session_id: str,
    request: ChunkDeleteRequest,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> ChunkOperationResponse:
    """
    Delete chunks from Qdrant vector database.
    
    Args:
        session_id: Session identifier
        request: Chunk delete request with chunk IDs
        db_manager: Database manager instance
        
    Returns:
        ChunkOperationResponse: Delete operation result
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        start_time = datetime.utcnow()
        
        # Perform deletion using database manager
        result = await db_manager.delete_chunks(
            chunk_ids=request.chunk_ids
        )
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return ChunkOperationResponse(
            status="success" if result.get("status") == "success" else "partial_failure",
            chunks_affected=len(request.chunk_ids),
            processing_time_ms=processing_time,
            errors=result.get("errors") if result.get("errors") else None
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete chunks: {str(e)}"
        )
