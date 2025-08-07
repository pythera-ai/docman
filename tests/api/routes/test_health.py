"""
Test cases for Health Monitoring API endpoints.
Tests all health-related operations including system monitoring, database health, and metrics collection.
"""
import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from datetime import datetime
from typing import Dict, Any

from src.api.routes.health import router
from src.api.services.database_manager import DatabaseManager
from src.core.models import HealthStatus, DatabaseHealth, DetailedHealthResponse
from src.core.exceptions import DatabaseConnectionException


class TestBasicHealthCheck:
    """Test basic health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test basic health check endpoint."""
        from src.api.routes.health import health_check
        
        # Act
        result = await health_check()
        
        # Assert
        assert isinstance(result, HealthStatus)
        assert result.status == "healthy"
        assert result.version == "1.0.0"
        assert isinstance(result.timestamp, datetime)
        assert result.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_health_check_uptime_calculation(self):
        """Test that uptime is calculated correctly."""
        from src.api.routes.health import health_check
        
        # Act - call twice with a small delay
        result1 = await health_check()
        
        # Small delay simulation
        import asyncio
        await asyncio.sleep(0.01)
        
        result2 = await health_check()
        
        # Assert
        assert result2.uptime_seconds >= result1.uptime_seconds
        assert result2.timestamp > result1.timestamp


class TestDetailedHealthCheck:
    """Test detailed health check functionality."""

    @pytest.mark.asyncio
    async def test_detailed_health_check_success(self, mock_db_manager):
        """Test successful detailed health check."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        from src.api.routes.health import detailed_health_check
        
        # Act
        result = await detailed_health_check(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, DetailedHealthResponse)
        assert result.status == "healthy"
        assert isinstance(result.databases, DatabaseHealth)
        assert result.databases.overall is True
        assert result.databases.minio is True
        assert result.databases.qdrant is True
        assert result.databases.postgres is True
        
        # Check system info structure
        assert "uptime_seconds" in result.system
        assert "configuration" in result.system
        assert "minio_endpoint" in result.system["configuration"]
        assert "qdrant_url" in result.system["configuration"]
        assert "postgres_host" in result.system["configuration"]
        
        # Check performance info structure
        assert "avg_response_time_ms" in result.performance
        assert "requests_per_minute" in result.performance
        assert "active_connections" in result.performance
        assert "memory_usage_mb" in result.performance
        
        mock_db_manager.is_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_detailed_health_check_unhealthy_database(self, mock_db_manager):
        """Test detailed health check with unhealthy database."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "overall": False,
            "minio": True,
            "qdrant": False,  # Qdrant is down
            "postgres": True
        }
        
        from src.api.routes.health import detailed_health_check
        
        # Act
        result = await detailed_health_check(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "unhealthy"
        assert result.databases.overall is False
        assert result.databases.qdrant is False
        assert result.databases.minio is True  # Other services still healthy
        assert result.databases.postgres is True

    @pytest.mark.asyncio
    async def test_detailed_health_check_partial_database_failure(self, mock_db_manager):
        """Test detailed health check with partial database failures."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "overall": False,
            "minio": False,  # MinIO is down
            "qdrant": True,
            "postgres": False  # Postgres is also down
        }
        
        from src.api.routes.health import detailed_health_check
        
        # Act
        result = await detailed_health_check(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.status == "unhealthy"
        assert result.databases.overall is False
        assert result.databases.minio is False
        assert result.databases.qdrant is True  # Only Qdrant is healthy
        assert result.databases.postgres is False

    @pytest.mark.asyncio
    async def test_detailed_health_check_exception(self, mock_db_manager):
        """Test detailed health check with exception during health check."""
        # Arrange
        mock_db_manager.is_healthy.side_effect = Exception("Health check failed")
        
        from src.api.routes.health import detailed_health_check
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await detailed_health_check(
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Health check failed" in str(exc_info.value.detail)


class TestDatabaseHealthCheck:
    """Test database-specific health check functionality."""

    @pytest.mark.asyncio
    async def test_database_health_check_success(self, mock_db_manager):
        """Test successful database health check."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        from src.api.routes.health import database_health_check
        
        # Act
        result = await database_health_check(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, DatabaseHealth)
        assert result.overall is True
        assert result.minio is True
        assert result.qdrant is True
        assert result.postgres is True
        mock_db_manager.is_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_health_check_mixed_status(self, mock_db_manager):
        """Test database health check with mixed service status."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "overall": False,
            "minio": True,
            "qdrant": False,
            "postgres": True
        }
        
        from src.api.routes.health import database_health_check
        
        # Act
        result = await database_health_check(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result.overall is False
        assert result.minio is True
        assert result.qdrant is False
        assert result.postgres is True

    @pytest.mark.asyncio
    async def test_database_health_check_exception(self, mock_db_manager):
        """Test database health check with exception."""
        # Arrange
        mock_db_manager.is_healthy.side_effect = Exception("Database check failed")
        
        from src.api.routes.health import database_health_check
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await database_health_check(
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Database health check failed" in str(exc_info.value.detail)


class TestSystemMetrics:
    """Test system metrics functionality."""

    @pytest.mark.asyncio
    async def test_get_metrics_success(self, mock_db_manager):
        """Test successful metrics retrieval."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        from src.api.routes.health import get_metrics
        
        # Act
        result = await get_metrics(
            db_manager=mock_db_manager
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert "database_connections" in result
        assert "performance" in result
        assert "system" in result
        
        # Check database connections structure
        db_connections = result["database_connections"]
        assert "minio" in db_connections
        assert "qdrant" in db_connections
        assert "postgres" in db_connections
        assert db_connections["minio"] is True
        
        # Check performance structure
        performance = result["performance"]
        assert "avg_response_time_ms" in performance
        assert "requests_per_minute" in performance
        assert "active_sessions" in performance
        assert "total_documents" in performance
        assert "total_searches" in performance
        
        # Check system structure
        system = result["system"]
        assert "version" in system
        assert "environment" in system
        assert "configuration_loaded" in system
        assert system["version"] == "1.0.0"
        
        mock_db_manager.is_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_database_issues(self, mock_db_manager):
        """Test metrics retrieval with database issues."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "minio": False,
            "qdrant": True,
            "postgres": False
        }
        
        from src.api.routes.health import get_metrics
        
        # Act
        result = await get_metrics(
            db_manager=mock_db_manager
        )
        
        # Assert
        db_connections = result["database_connections"]
        assert db_connections["minio"] is False
        assert db_connections["qdrant"] is True
        assert db_connections["postgres"] is False

    @pytest.mark.asyncio
    async def test_get_metrics_exception(self, mock_db_manager):
        """Test metrics retrieval with exception."""
        # Arrange
        mock_db_manager.is_healthy.side_effect = Exception("Metrics collection failed")
        
        from src.api.routes.health import get_metrics
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_metrics(
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to retrieve metrics" in str(exc_info.value.detail)


class TestComponentStatus:
    """Test individual component status functionality."""

    @pytest.mark.asyncio
    async def test_component_status_api_success(self, mock_db_manager):
        """Test API component status check."""
        from src.api.routes.health import component_status
        
        # Act
        result = await component_status(
            component="api",
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["component"] == "api"
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert "details" in result
        assert result["details"]["version"] == "1.0.0"
        assert result["details"]["environment"] == "development"

    @pytest.mark.asyncio
    async def test_component_status_minio_healthy(self, mock_db_manager):
        """Test MinIO component status when healthy."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        from src.api.routes.health import component_status
        
        # Act
        result = await component_status(
            component="minio",
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["component"] == "minio"
        assert result["status"] == "healthy"
        assert result["connection_status"] is True
        assert "details" in result
        assert "connection_info" in result["details"]
        mock_db_manager.is_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_component_status_qdrant_unhealthy(self, mock_db_manager):
        """Test Qdrant component status when unhealthy."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "minio": True,
            "qdrant": False,  # Qdrant is down
            "postgres": True
        }
        
        from src.api.routes.health import component_status
        
        # Act
        result = await component_status(
            component="qdrant",
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["component"] == "qdrant"
        assert result["status"] == "unhealthy"
        assert result["connection_status"] is False

    @pytest.mark.asyncio
    async def test_component_status_postgres_healthy(self, mock_db_manager):
        """Test Postgres component status when healthy."""
        # Arrange
        mock_db_manager.is_healthy.return_value = {
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        from src.api.routes.health import component_status
        
        # Act
        result = await component_status(
            component="postgres",
            db_manager=mock_db_manager
        )
        
        # Assert
        assert result["component"] == "postgres"
        assert result["status"] == "healthy"
        assert result["connection_status"] is True

    @pytest.mark.asyncio
    async def test_component_status_invalid_component(self, mock_db_manager):
        """Test component status with invalid component name."""
        from src.api.routes.health import component_status
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await component_status(
                component="invalid_component",
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 400
        assert "Unknown component: invalid_component" in str(exc_info.value.detail)
        assert "Valid components:" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_component_status_database_exception(self, mock_db_manager):
        """Test component status with database exception."""
        # Arrange
        mock_db_manager.is_healthy.side_effect = Exception("Component check failed")
        
        from src.api.routes.health import component_status
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await component_status(
                component="minio",
                db_manager=mock_db_manager
            )
        
        assert exc_info.value.status_code == 500
        assert "Component status check failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_component_status_all_valid_components(self, mock_db_manager):
        """Test all valid component names."""
        # Arrange
        valid_components = ["api", "minio", "qdrant", "postgres"]
        
        mock_db_manager.is_healthy.return_value = {
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        from src.api.routes.health import component_status
        
        # Act & Assert for each component
        for component in valid_components:
            result = await component_status(
                component=component,
                db_manager=mock_db_manager
            )
            
            assert result["component"] == component
            assert "status" in result
            assert "timestamp" in result


class TestHealthIntegration:
    """Integration tests for health monitoring workflow."""

    @pytest.mark.asyncio
    async def test_health_monitoring_workflow(self, mock_db_manager):
        """Test complete health monitoring workflow."""
        # Import functions
        from src.api.routes.health import (
            health_check, detailed_health_check, 
            database_health_check, get_metrics, component_status
        )
        
        # Setup - Mock healthy system
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        # 1. Basic health check
        basic_health = await health_check()
        assert basic_health.status == "healthy"
        
        # 2. Detailed health check
        detailed_health = await detailed_health_check(
            db_manager=mock_db_manager
        )
        assert detailed_health.status == "healthy"
        assert detailed_health.databases.overall is True
        
        # 3. Database-specific health check
        db_health = await database_health_check(
            db_manager=mock_db_manager
        )
        assert db_health.overall is True
        
        # 4. System metrics
        metrics = await get_metrics(
            db_manager=mock_db_manager
        )
        assert "database_connections" in metrics
        assert metrics["database_connections"]["minio"] is True
        
        # 5. Individual component checks
        components = ["api", "minio", "qdrant", "postgres"]
        for component in components:
            component_result = await component_status(
                component=component,
                db_manager=mock_db_manager
            )
            assert component_result["component"] == component
            
            if component == "api":
                assert component_result["status"] == "healthy"
            else:
                # Database components should be healthy based on mock
                assert component_result["status"] == "healthy"
                assert component_result["connection_status"] is True

    @pytest.mark.asyncio
    async def test_health_monitoring_degraded_system(self, mock_db_manager):
        """Test health monitoring with degraded system performance."""
        # Import functions
        from src.api.routes.health import (
            detailed_health_check, database_health_check, 
            get_metrics, component_status
        )
        
        # Setup - Mock partially degraded system
        mock_db_manager.is_healthy.return_value = {
            "overall": False,
            "minio": True,     # MinIO is working
            "qdrant": False,   # Qdrant is down
            "postgres": True   # Postgres is working
        }
        
        # 1. Detailed health check should show unhealthy
        detailed_health = await detailed_health_check(
            db_manager=mock_db_manager
        )
        assert detailed_health.status == "unhealthy"
        assert detailed_health.databases.overall is False
        
        # 2. Database health should reflect partial failure
        db_health = await database_health_check(
            db_manager=mock_db_manager
        )
        assert db_health.overall is False
        assert db_health.minio is True
        assert db_health.qdrant is False
        assert db_health.postgres is True
        
        # 3. Metrics should show database connection issues
        metrics = await get_metrics(
            db_manager=mock_db_manager
        )
        db_connections = metrics["database_connections"]
        assert db_connections["minio"] is True
        assert db_connections["qdrant"] is False
        assert db_connections["postgres"] is True
        
        # 4. Component status should reflect individual service status
        minio_status = await component_status(
            component="minio",
            db_manager=mock_db_manager
        )
        assert minio_status["status"] == "healthy"
        
        qdrant_status = await component_status(
            component="qdrant",
            db_manager=mock_db_manager
        )
        assert qdrant_status["status"] == "unhealthy"
        
        postgres_status = await component_status(
            component="postgres",
            db_manager=mock_db_manager
        )
        assert postgres_status["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_monitoring_complete_system_failure(self, mock_db_manager):
        """Test health monitoring during complete system failure."""
        # Import functions
        from src.api.routes.health import (
            detailed_health_check, database_health_check, component_status
        )
        
        # Setup - Mock complete system failure
        mock_db_manager.is_healthy.return_value = {
            "overall": False,
            "minio": False,
            "qdrant": False,
            "postgres": False
        }
        
        # 1. Detailed health check should show unhealthy
        detailed_health = await detailed_health_check(
            db_manager=mock_db_manager
        )
        assert detailed_health.status == "unhealthy"
        
        # 2. All database components should be unhealthy
        db_health = await database_health_check(
            db_manager=mock_db_manager
        )
        assert db_health.overall is False
        assert db_health.minio is False
        assert db_health.qdrant is False
        assert db_health.postgres is False
        
        # 3. All database components should report as unhealthy
        for component in ["minio", "qdrant", "postgres"]:
            status = await component_status(
                component=component,
                db_manager=mock_db_manager
            )
            assert status["status"] == "unhealthy"
            assert status["connection_status"] is False
        
        # 4. API component should still be healthy (application layer)
        api_status = await component_status(
            component="api",
            db_manager=mock_db_manager
        )
        assert api_status["status"] == "healthy"  # API itself is still running

    @pytest.mark.asyncio
    async def test_health_check_timing_consistency(self, mock_db_manager):
        """Test that health check timings are consistent and reasonable."""
        # Import functions
        from src.api.routes.health import health_check, detailed_health_check
        
        # Setup
        mock_db_manager.is_healthy.return_value = {
            "overall": True,
            "minio": True,
            "qdrant": True,
            "postgres": True
        }
        
        # Act - Perform multiple health checks
        results = []
        for _ in range(3):
            basic = await health_check()
            detailed = await detailed_health_check(db_manager=mock_db_manager)
            results.append((basic.timestamp, detailed.timestamp))
        
        # Assert - Timestamps should be in ascending order
        for i in range(1, len(results)):
            prev_basic, prev_detailed = results[i-1]
            curr_basic, curr_detailed = results[i]
            
            # Each subsequent check should have later timestamps
            assert curr_basic >= prev_basic
            assert curr_detailed >= prev_detailed
            
            # Within each check, detailed should be after or same as basic
            assert curr_detailed >= curr_basic
