# src/api/dependencies.py
"""
Shared dependencies for the FastAPI application.
"""

from fastapi import Depends, HTTPException
from starlette.requests import Request
from src.api.services.database_manager import DatabaseManager


async def get_database_manager(request: Request) -> DatabaseManager:
    """
    Get the database manager instance from the application state.
    
    This dependency retrieves the DatabaseManager that was initialized
    during the application lifespan and stored in the app state.
    
    Args:
        request: FastAPI request object containing app state
        
    Returns:
        DatabaseManager: Initialized database manager instance
        
    Raises:
        HTTPException: If database manager is not initialized
    """
    db_manager = getattr(request.app.state, 'db_manager', None)
    
    if db_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Database manager not initialized. Please check server startup logs."
        )
    
    return db_manager
