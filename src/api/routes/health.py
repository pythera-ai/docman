"""
Health monitoring routes for system status and diagnostics.
Implements FR007 functional requirements.
"""
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.config import config
from src.api.services.database_manager import DatabaseManager
from src.core.exceptions import DatabaseConnectionException


router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    """Health status response model"""
    status: str
    timestamp: datetime
    uptime_seconds: float
    version: str = "1.0.0"


class DatabaseHealth(BaseModel):
    """Database health status model"""
    minio: bool
    qdrant: bool
    postgres: bool
    overall: bool


class DetailedHealthResponse(BaseModel):
    """Detailed health response"""
    status: str
    timestamp: datetime
    databases: DatabaseHealth
    system: Dict[str, Any]
    performance: Dict[str, Any]


# Store application start time for uptime calculation
_app_start_time = datetime.utcnow()


# Dependency to get database manager instance
async def get_database_manager() -> DatabaseManager:
    """Get database manager instance."""
    return DatabaseManager()


@router.get("/", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    FR007: Health Monitoring - Basic health check endpoint.
    
    Returns:
        HealthStatus: Basic health information
    """
    current_time = datetime.utcnow()
    uptime = (current_time - _app_start_time).total_seconds()
    
    return HealthStatus(
        status="healthy",
        timestamp=current_time,
        uptime_seconds=uptime
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DetailedHealthResponse:
    """
    FR007: Health Monitoring - Detailed health check including database status.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        DetailedHealthResponse: Comprehensive health information
        
    Raises:
        HTTPException: If health check fails
    """
    try:
        current_time = datetime.utcnow()
        uptime = (current_time - _app_start_time).total_seconds()
        
        # Check database health
        db_health = db_manager.is_healthy()
        
        # System information
        system_info = {
            "uptime_seconds": uptime,
            "configuration": {
                "minio_endpoint": config.minio.endpoint,
                "qdrant_url": config.qdrant.url,
                "postgres_host": config.postgres.host,
                "default_collection": config.qdrant.default_collection_name,
                "default_bucket": config.minio.default_bucket
            }
        }
        
        # Performance metrics (placeholder)
        performance_info = {
            "avg_response_time_ms": 0,
            "requests_per_minute": 0,
            "active_connections": 0,
            "memory_usage_mb": 0
        }
        
        # Determine overall status
        overall_status = "healthy" if db_health["overall"] else "unhealthy"
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=current_time,
            databases=DatabaseHealth(**db_health),
            system=system_info,
            performance=performance_info
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/databases", response_model=DatabaseHealth)
async def database_health_check(
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DatabaseHealth:
    """
    FR007: Health Monitoring - Database-specific health check.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        DatabaseHealth: Database connection status
        
    Raises:
        HTTPException: If database health check fails
    """
    try:
        db_health = db_manager.is_healthy()
        return DatabaseHealth(**db_health)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database health check failed: {str(e)}"
        )


@router.get("/metrics")
async def get_metrics(
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    FR007: Health Monitoring - System metrics endpoint.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        Dict: System performance metrics
        
    Raises:
        HTTPException: If metrics retrieval fails
    """
    try:
        current_time = datetime.utcnow()
        uptime = (current_time - _app_start_time).total_seconds()
        
        # Get database health for connection status
        db_health = db_manager.is_healthy()
        
        metrics = {
            "timestamp": current_time.isoformat(),
            "uptime_seconds": uptime,
            "database_connections": {
                "minio": db_health["minio"],
                "qdrant": db_health["qdrant"],
                "postgres": db_health["postgres"]
            },
            "performance": {
                "avg_response_time_ms": 0,  # Placeholder
                "requests_per_minute": 0,   # Placeholder
                "active_sessions": 0,       # Placeholder
                "total_documents": 0,       # Placeholder
                "total_searches": 0         # Placeholder
            },
            "system": {
                "version": "1.0.0",
                "environment": "development",  # Could be read from config
                "configuration_loaded": True
            }
        }
        
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.get("/status/{component}")
async def component_status(
    component: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> Dict[str, Any]:
    """
    FR007: Health Monitoring - Individual component status check.
    
    Args:
        component: Component name (minio, qdrant, postgres, api)
        db_manager: Database manager instance
        
    Returns:
        Dict: Component-specific status information
        
    Raises:
        HTTPException: If component check fails or component is unknown
    """
    try:
        valid_components = ["minio", "qdrant", "postgres", "api"]
        
        if component not in valid_components:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown component: {component}. Valid components: {valid_components}"
            )
        
        current_time = datetime.utcnow()
        
        if component == "api":
            uptime = (current_time - _app_start_time).total_seconds()
            return {
                "component": component,
                "status": "healthy",
                "timestamp": current_time.isoformat(),
                "uptime_seconds": uptime,
                "details": {
                    "version": "1.0.0",
                    "environment": "development"
                }
            }
        
        # For database components
        db_health = db_manager.is_healthy()
        component_healthy = db_health.get(component, False)
        
        return {
            "component": component,
            "status": "healthy" if component_healthy else "unhealthy",
            "timestamp": current_time.isoformat(),
            "connection_status": component_healthy,
            "details": {
                "host": getattr(config, component).host if hasattr(config, component) else "unknown",
                "last_check": current_time.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Component status check failed: {str(e)}"
        )
