"""
Session management routes - CRUD operations for sessions.
Supports the 4 core features:
1. Session CRUD operations
2. Document management integration
3. Chunks management integration
4. Metrics and logging
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query

from src.core.config import config
from src.core.models import (
    SessionInfo, SessionCreateRequest, SessionUpdateRequest, AdminStatsResponse
)
from src.api.services.database_manager import DatabaseManager
from src.core.exceptions import DatabaseConnectionException
from src.api.dependencies import get_database_manager


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


# =============================================
# SESSION CRUD OPERATIONS
# =============================================

@router.post("/", response_model=SessionInfo)
async def create_session(
    request: SessionCreateRequest,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> SessionInfo:
    """
    Create a new session (Core Feature: Session CRUD).
    
    Args:
        request: Session creation parameters
        db_manager: Database manager instance
        
    Returns:
        SessionInfo: Created session information
        
    Raises:
        HTTPException: If session creation fails
    """
    try:
        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)
        
        result = await db_manager.create_session(
            user_id=request.user_id,
            expires_at=expires_at,
            metadata=request.metadata,
            temp_collection_name=request.temp_collection_name
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create session: {result['error']}"
            )
        
        session_data = result["session"]
        return SessionInfo(**session_data)
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Session creation failed: {str(e)}"
        )


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> SessionInfo:
    """
    Get session information by ID (Core Feature: Session CRUD).
    
    Args:
        session_id: Session identifier
        db_manager: Database manager instance
        
    Returns:
        SessionInfo: Session information
        
    Raises:
        HTTPException: If session not found
    """
    try:
        session_data = await db_manager.get_session(session_id)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        return SessionInfo(**session_data)
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session: {str(e)}"
        )


@router.get("/users/{user_id}", response_model=List[SessionInfo])
async def get_user_sessions(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter by session status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> List[SessionInfo]:
    """
    Get all sessions for a specific user (Core Feature: Session CRUD).
    
    Args:
        user_id: User identifier
        status: Optional status filter
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip
        db_manager: Database manager instance
        
    Returns:
        List[SessionInfo]: List of user sessions
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        result = await db_manager.get_user_sessions(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get user sessions: {result['error']}"
            )
        
        return [SessionInfo(**session) for session in result["sessions"]]
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user sessions: {str(e)}"
        )


@router.put("/{session_id}", response_model=SessionInfo)
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> SessionInfo:
    """
    Update session information (Core Feature: Session CRUD).
    
    Args:
        session_id: Session identifier
        request: Update parameters
        db_manager: Database manager instance
        
    Returns:
        SessionInfo: Updated session information
        
    Raises:
        HTTPException: If update fails
    """
    try:
        # Calculate new expiration if extending
        expires_at = None
        if request.extend_hours:
            current_session = await db_manager.get_session(session_id)
            if current_session:
                current_expires = datetime.fromisoformat(current_session["expires_at"].replace('Z', '+00:00'))
                expires_at = current_expires + timedelta(hours=request.extend_hours)
        
        result = await db_manager.update_session(
            session_id=session_id,
            status=request.status,
            metadata=request.metadata,
            temp_collection_name=request.temp_collection_name,
            expires_at=expires_at
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=404 if "not found" in result["error"].lower() else 500,
                detail=f"Failed to update session: {result['error']}"
            )
        
        session_data = result["session"]
        return SessionInfo(**session_data)
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Session update failed: {str(e)}"
        )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    Delete a session (Core Feature: Session CRUD).
    
    Args:
        session_id: Session identifier
        db_manager: Database manager instance
        
    Returns:
        Dict: Deletion status
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        result = await db_manager.delete_session(session_id)
        
        if result.get("error"):
            raise HTTPException(
                status_code=404 if "not found" in result["error"].lower() else 500,
                detail=f"Failed to delete session: {result['error']}"
            )
        
        return {
            "message": "Session deleted successfully",
            "session_id": session_id,
            "deleted": result.get("deleted", False)
        }
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Session deletion failed: {str(e)}"
        )



@router.post("/expire")
async def expire_old_sessions(
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    Mark expired sessions as 'expired' (Core Feature: Session Management + Metrics).
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        Dict: Expiration results
        
    Raises:
        HTTPException: If expiration fails
    """
    try:
        result = await db_manager.expire_old_sessions()
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to expire sessions: {result['error']}"
            )
        
        return {
            "message": "Session expiration completed",
            "expired_count": result.get("expired_count", 0),
            "processing_time_ms": result.get("processing_time_ms", 0)
        }
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Session expiration failed: {str(e)}"
        )


@router.get("/{session_id}/documents")
async def get_session_documents(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    Get all documents for a specific session (Core Feature: Session + Document integration).
    
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


# =============================================  
# ADMINISTRATION & MONITORING ENDPOINTS
# =============================================

@router.get("/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    user_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> AdminStatsResponse:
    """
    Get administrative statistics (Core Feature: Metrics and Logging).
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        AdminStatsResponse: System statistics
        
    Raises:
        HTTPException: If stats retrieval fails
    """
    try:
        # Get database health status
        db_health = db_manager.is_healthy()
        
        # Calculate system uptime (placeholder - would need app start time tracking)
        uptime_seconds = 0.0
        
        # Get real statistics from database
        total_sessions = 0
        active_sessions = 0
        total_documents = 0
        
        try:
            # Get session statistics by querying for different statuses
            all_sessions_result = await db_manager.get_user_sessions(user_id, limit=1000)  # Get all sessions
            if not all_sessions_result.get("error"):
                total_sessions = all_sessions_result.get("total_found", 0)
            
            active_sessions_result = await db_manager.get_user_sessions(user_id, status="active", limit=1000)
            if not active_sessions_result.get("error"):
                active_sessions = active_sessions_result.get("total_found", 0)
                
            # Note: For total_documents, we'd need a method to count all documents
            # This could be added to the database manager if needed
            
        except Exception as e:
            logger.warning(f"Could not get detailed statistics: {e}")
        
        return AdminStatsResponse(
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            total_documents=total_documents,
            total_searches=0,  # Would need search tracking
            system_uptime_seconds=uptime_seconds,
            database_status=db_health
        )
        
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve admin stats: {str(e)}"
        )


@router.post("/admin/cleanup")
async def perform_system_cleanup(
    cleanup_type: str = Query("normal", description="Type of cleanup: normal, deep, emergency"),
    dry_run: bool = Query(False, description="Perform dry run without actual cleanup"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    Perform system cleanup operations (Core Feature: Metrics and System Management).
    
    Args:
        cleanup_type: Type of cleanup to perform
        dry_run: Whether to perform a dry run
        db_manager: Database manager instance
        
    Returns:
        Dict: Cleanup results
        
    Raises:
        HTTPException: If cleanup fails
    """
    try:
        valid_cleanup_types = ["normal", "deep", "emergency"]
        if cleanup_type not in valid_cleanup_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cleanup type. Valid types: {valid_cleanup_types}"
            )
        
        current_time = datetime.utcnow()
        
        # Initialize cleanup results
        cleanup_results = {
            "expired_sessions_cleaned": 0,
            "orphaned_documents_removed": 0,
            "temporary_files_deleted": 0,
            "space_freed_mb": 0
        }
        
        # Perform actual cleanup operations based on cleanup type
        if not dry_run:
            try:
                # 1. Clean up expired sessions
                if cleanup_type in ["normal", "deep", "emergency"]:
                    expire_result = await db_manager.expire_old_sessions()
                    if not expire_result.get("error"):
                        cleanup_results["expired_sessions_cleaned"] = expire_result.get("expired_count", 0)
                
                # 2. For deep cleanup, could add more operations
                if cleanup_type in ["deep", "emergency"]:
                    # Could implement additional cleanup like:
                    # - Remove orphaned documents
                    # - Clean up temporary collections
                    # - Optimize database indices
                    pass
                    
            except Exception as e:
                logger.warning(f"Cleanup operation encountered issues: {e}")
        
        return {
            "cleanup_type": cleanup_type,
            "dry_run": dry_run,
            "timestamp": current_time.isoformat(),
            "results": cleanup_results,
            "message": f"{'Dry run' if dry_run else 'Actual'} {cleanup_type} cleanup completed"
        }
        
    except HTTPException:
        raise
    except DatabaseConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup operation failed: {str(e)}"
        )
