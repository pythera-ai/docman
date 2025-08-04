# src/api/services/database_manager.py
"""
Database Manager Service

Centralized management of all database connections and operations.
Provides a unified interface for MinIO, Qdrant, and PostgreSQL operations.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from src.core import (
    config,
    DatabaseConnectionException,
    metrics
)

from src.db.minio_db import MinioDB
from src.db.qdrant_db import QdrantChunksDB
from src.db.postgres_db import PostgresDB

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Centralized database manager for all storage operations
    """
    
    def __init__(self):
        self.minio_client: Optional[MinioDB] = None
        self.qdrant_client: Optional[QdrantChunksDB] = None
        self.postgres_client: Optional[PostgresDB] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize all database connections"""
        logger.info("🔌 Initializing database connections...")
        
        try:
            # Initialize MinIO
            await self._init_minio()
            
            # Initialize Qdrant
            await self._init_qdrant()
            
            # Initialize PostgreSQL
            await self._init_postgres()
            
            self._initialized = True
            logger.info("✅ All database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize databases: {e}")
            await self.cleanup()
            raise DatabaseConnectionException("all", {"error": str(e)})
    
    async def _init_minio(self):
        """Initialize MinIO connection"""
        try:
            logger.info("🗄️ Connecting to MinIO...")
            
            self.minio_client = MinioDB(
                endpoint=config.minio.endpoint,
                access_key=config.minio.access_key,
                secret_key=config.minio.secret_key,
                secure=config.minio.secure
            )
            
            # Test connection by creating default bucket
            if self.minio_client._client:
                success = self.minio_client.create_bucket(config.minio.default_bucket)
                if success:
                    logger.info("✅ MinIO connection established")
                    metrics.record_database_connection("minio", 1)
                else:
                    raise DatabaseConnectionException("MinIO", {"endpoint": config.minio.endpoint})
            else:
                raise DatabaseConnectionException("MinIO", {"endpoint": config.minio.endpoint})
                
        except Exception as e:
            logger.error(f"❌ MinIO connection failed: {e}")
            metrics.record_database_error("minio", "connection_failed")
            raise DatabaseConnectionException("MinIO", {"endpoint": config.minio.endpoint, "error": str(e)})
    
    async def _init_qdrant(self):
        """Initialize Qdrant connection"""
        try:
            logger.info("🔍 Connecting to Qdrant...")
            
            self.qdrant_client = QdrantChunksDB(
                url=config.qdrant.url,
                api_key=config.qdrant.api_key
            )
            
            # Test connection by creating default collection
            if self.qdrant_client._client:
                success = self.qdrant_client.create_collection(
                    collection_name=config.qdrant.default_collection_name,
                    dimension=config.qdrant.vector_dimension,
                    distance=config.qdrant.distance_metric
                )
                if success:
                    logger.info("✅ Qdrant connection established")
                    metrics.record_database_connection("qdrant", 1)
                else:
                    raise DatabaseConnectionException("Qdrant", {"url": config.qdrant.url})
            else:
                raise DatabaseConnectionException("Qdrant", {"url": config.qdrant.url})
                
        except Exception as e:
            logger.error(f"❌ Qdrant connection failed: {e}")
            metrics.record_database_error("qdrant", "connection_failed")
            raise DatabaseConnectionException("Qdrant", {"url": config.qdrant.url, "error": str(e)})
    
    async def _init_postgres(self):
        """Initialize PostgreSQL connection"""
        try:
            logger.info("🐘 Connecting to PostgreSQL...")
            
            self.postgres_client = PostgresDB(
                host=config.postgres.host,
                port=config.postgres.port,
                database=config.postgres.database,
                username=config.postgres.username,
                password=config.postgres.password
            )
            
            # Test connection
            if self.postgres_client._connection:
                logger.info("✅ PostgreSQL connection established")
                metrics.record_database_connection("postgres", 1)
            else:
                raise DatabaseConnectionException("PostgreSQL", {"host": config.postgres.host, "database": config.postgres.database})
                
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            metrics.record_database_error("postgres", "connection_failed")
            raise DatabaseConnectionException("PostgreSQL", {"host": config.postgres.host, "database": config.postgres.database, "error": str(e)})
    
    async def cleanup(self):
        """Cleanup all database connections"""
        logger.info("🧹 Cleaning up database connections...")
        
        # Record final metrics
        metrics.record_database_connection("minio", 0)
        metrics.record_database_connection("qdrant", 0)
        metrics.record_database_connection("postgres", 0)
        
        self._initialized = False
        logger.info("✅ Database cleanup completed")
    
    def is_healthy(self) -> Dict[str, bool]:
        """Check health status of all databases"""
        health_status = {
            "minio": False,
            "qdrant": False,
            "postgres": False,
            "overall": False
        }
        
        try:
            # Check MinIO
            if self.minio_client and self.minio_client._check_client():
                health_status["minio"] = True
            
            # Check Qdrant
            if self.qdrant_client and self.qdrant_client._check_client():
                health_status["qdrant"] = True
            
            # Check PostgreSQL
            if self.postgres_client and self.postgres_client._check_connection():
                health_status["postgres"] = True
            
            # Overall health
            health_status["overall"] = all([
                health_status["minio"],
                health_status["qdrant"],
                health_status["postgres"]
            ])
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        
        return health_status
    
    # Document Operations
    async def upload_document(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        file_hash: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload document to MinIO and store metadata in PostgreSQL"""
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            # Upload to MinIO
            if not self.minio_client:
                raise DatabaseConnectionException("MinIO", {"reason": "client_not_initialized"})
            
            minio_points = [{
                'document_id': document_id,
                'file_data': file_data,
                'filename': filename,
                'file_size': len(file_data),
                'content_type': content_type,
                'file_hash': file_hash
            }]
            
            minio_result = self.minio_client.insert(
                points=minio_points,
                bucket_name=config.minio.default_bucket
            )
            
            if minio_result.get('documents'):
                # Store metadata in PostgreSQL
                if not self.postgres_client:
                    raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
                
                postgres_points = [{
                    'document_id': document_id,
                    'filename': filename,
                    'file_size': len(file_data),
                    'content_type': content_type,
                    'file_hash': file_hash,
                    'chunks_count': 0,  # Will be updated after chunking
                    'processing_status': 'uploaded',
                    'metadata': metadata or {}
                }]
                
                postgres_result = self.postgres_client.insert(points=postgres_points)
                
                return {
                    "status": "success",
                    "minio_result": minio_result,
                    "postgres_result": postgres_result
                }
            else:
                raise Exception("MinIO upload failed")
                
        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            raise
    
    async def store_chunks(
        self,
        chunks: List[Dict[str, Any]],
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store document chunks in Qdrant"""
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        collection = collection_name or config.qdrant.default_collection_name
        
        try:
            if not self.qdrant_client:
                raise DatabaseConnectionException("Qdrant", {"reason": "client_not_initialized"})
            
            result = self.qdrant_client.insert(
                points=chunks,
                collection_name=collection
            )
            return result
            
        except Exception as e:
            logger.error(f"Chunk storage failed: {e}")
            raise
    
    async def search_documents(
        self,
        query_vector: List[float],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search documents using vector similarity"""
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        collection = collection_name or config.qdrant.default_collection_name
        
        try:
            if not self.qdrant_client:
                raise DatabaseConnectionException("Qdrant", {"reason": "client_not_initialized"})
            
            search_params = {
                "query_vector": query_vector,
                "collection_name": collection,
                "limit": limit
            }
            
            # Add filters if provided
            if filters:
                search_params.update(filters)
            
            result = self.qdrant_client.search(**search_params)
            return result
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            raise
    
    async def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata from PostgreSQL"""
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.search(
                filters={"document_id": document_id},
                limit=1
            )
            
            if result.get("documents"):
                return result["documents"][0]
            return None
            
        except Exception as e:
            logger.error(f"Get document metadata failed: {e}")
            raise
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete document from all databases"""
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        results = {}
        
        try:
            # Delete from MinIO
            if not self.minio_client:
                raise DatabaseConnectionException("MinIO", {"reason": "client_not_initialized"})
            minio_result = self.minio_client.delete([document_id])
            results["minio"] = minio_result
            
            # Delete chunks from Qdrant
            if not self.qdrant_client:
                raise DatabaseConnectionException("Qdrant", {"reason": "client_not_initialized"})
            qdrant_result = self.qdrant_client.delete(
                points_ids=[document_id],
                by_document_id=True,
                collection_name=config.qdrant.default_collection_name
            )
            results["qdrant"] = qdrant_result
            
            # Delete metadata from PostgreSQL
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            postgres_result = self.postgres_client.delete([document_id])
            results["postgres"] = postgres_result
            
            return {
                "status": "success",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            results["error"] = str(e)
            return {
                "status": "failed",
                "results": results
            }
    
    async def update_document_metadata(
        self,
        document_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update document metadata in PostgreSQL"""
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            points = [{
                "document_id": document_id,
                **updates
            }]
            
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            result = self.postgres_client.update(points=points)
            return result
            
        except Exception as e:
            logger.error(f"Document metadata update failed: {e}")
            raise
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        stats = {
            "databases": self.is_healthy(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Get collection info if available
            if self.qdrant_client and self.qdrant_client._check_client():
                collection_info = self.qdrant_client.get_collection_info(
                    config.qdrant.default_collection_name
                )
                stats["qdrant_collection"] = collection_info
        
        except Exception as e:
            logger.warning(f"Could not get system stats: {e}")
            stats["error"] = str(e)
        
        return stats

    # =============================================
    # SESSION MANAGEMENT METHODS
    # =============================================
    
    async def create_session(
        self,
        user_id: str,
        expires_at: datetime,
        metadata: Optional[Dict[str, Any]] = None,
        temp_collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for chat history and document management.
        
        Args:
            user_id: User identifier
            expires_at: When the session expires
            metadata: Optional session metadata
            temp_collection_name: Optional temporary collection name
            
        Returns:
            Dict: Session creation result
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.create_session(
                user_id=user_id,
                expires_at=expires_at,
                metadata=metadata,
                temp_collection_name=temp_collection_name
            )
            
            # Record metrics
            metrics.record_document_operation(
                operation="create_session",
                database="postgres",
                status="success" if result.get("session") else "error",
                duration=result.get("processing_time_ms", 0) / 1000,
                document_count=1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "create_session", "error": str(e)})
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict]: Session information or None if not found
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            return self.postgres_client.get_session(session_id)
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "get_session", "error": str(e)})
    
    async def get_user_sessions(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get sessions for a specific user.
        
        Args:
            user_id: User identifier
            status: Optional status filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Dict: Sessions and pagination info
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.get_user_sessions(
                user_id=user_id,
                status=status,
                limit=limit,
                offset=offset
            )
            
            # Record metrics
            metrics.record_document_operation(
                operation="get_user_sessions",
                database="postgres",
                status="success" if not result.get("error") else "error",
                duration=result.get("processing_time_ms", 0) / 1000,
                document_count=result.get("returned_count", 0)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "get_user_sessions", "error": str(e)})
    
    async def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        temp_collection_name: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Update session information.
        
        Args:
            session_id: Session identifier
            status: New status
            metadata: Metadata to merge
            temp_collection_name: New temp collection name
            expires_at: New expiration time
            
        Returns:
            Dict: Update result
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.update_session(
                session_id=session_id,
                status=status,
                metadata=metadata,
                temp_collection_name=temp_collection_name,
                expires_at=expires_at
            )
            
            # Record metrics
            metrics.record_document_operation(
                operation="update_session",
                database="postgres",
                status="success" if result.get("session") else "error",
                duration=result.get("processing_time_ms", 0) / 1000,
                document_count=1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "update_session", "error": str(e)})
    
    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict: Deletion result
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.delete_session(session_id)
            
            # Record metrics
            metrics.record_document_operation(
                operation="delete_session",
                database="postgres",
                status="success" if result.get("deleted") else "error",
                duration=result.get("processing_time_ms", 0) / 1000,
                document_count=1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "delete_session", "error": str(e)})
    
    async def expire_old_sessions(self) -> Dict[str, Any]:
        """
        Mark expired sessions as 'expired' based on expires_at timestamp.
        
        Returns:
            Dict: Expiration results
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.expire_old_sessions()
            
            # Record metrics
            metrics.record_document_operation(
                operation="expire_sessions",
                database="postgres",
                status="success" if not result.get("error") else "error",
                duration=result.get("processing_time_ms", 0) / 1000,
                document_count=result.get("expired_count", 0)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to expire old sessions: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "expire_sessions", "error": str(e)})
    
    async def get_session_documents(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get all documents for a specific session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Dict: Documents and pagination info
            
        Raises:
            DatabaseConnectionException: If PostgreSQL is not available
        """
        if not self._initialized:
            raise DatabaseConnectionException("system", {"reason": "not_initialized"})
        
        try:
            if not self.postgres_client:
                raise DatabaseConnectionException("PostgreSQL", {"reason": "client_not_initialized"})
            
            result = self.postgres_client.get_session_documents(
                session_id=session_id,
                limit=limit,
                offset=offset
            )
            
            # Record metrics
            metrics.record_document_operation(
                operation="get_session_documents",
                database="postgres",
                status="success" if not result.get("error") else "error",
                duration=result.get("processing_time_ms", 0) / 1000,
                document_count=result.get("returned_count", 0)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get session documents for {session_id}: {e}")
            raise DatabaseConnectionException("PostgreSQL", {"operation": "get_session_documents", "error": str(e)})
