import os
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict
from dataclasses import dataclass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    from psycopg2 import sql
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    psycopg2 = None
    RealDictCursor = None
    Json = None

from .interface import InterfaceDatabase


@dataclass
class DocumentRecord:
    """Document record structure matching the database schema"""
    document_id: str
    user_id: str
    filename: str
    file_type: str
    file_size: int
    minio_path: str
    processing_status: str = 'pending'
    chunks_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict] = None


class PostgresDB(InterfaceDatabase):
    """
    PostgreSQL database implementation for storing document metadata.
    Works with MinIO for file storage and provides metadata management.
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 5432,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ) -> None:
        if not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 package is not installed. Please install it with: pip install psycopg2-binary")
        
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        self.connection_params.update(kwargs)
        self._connection = None
        self._connect()
    
    def connect_client(self, url, **kwargs) -> Any:
        """Connect to PostgreSQL database"""
        if not POSTGRES_AVAILABLE:
            return None
            
        try:
            # Parse connection parameters
            host = kwargs.get('host') or url
            port = kwargs.get('port', 5432)
            database = kwargs.get('database')
            user = kwargs.get('user')
            password = kwargs.get('password')
            
            if not all([host, database, user, password]):
                logging.error("Missing required PostgreSQL connection parameters")
                return None
            
            if psycopg2 is None:
                raise ImportError("psycopg2 not available")
                
            connection = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            
            # Test connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                
            logging.info(f"Successfully connected to PostgreSQL at {host}:{port}")
            return connection
            
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {e}")
            return None
    
    def _connect(self) -> bool:
        """Establish database connection"""
        if not POSTGRES_AVAILABLE or psycopg2 is None:
            return False
            
        try:
            self._connection = psycopg2.connect(**self.connection_params)
            return True
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            return False
    
    def _check_connection(self) -> bool:
        """Check if database connection is active"""
        if not POSTGRES_AVAILABLE or self._connection is None:
            return self._connect()
        
        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except:
            return self._connect()
    
    def insert(self, points: List[Any], **kwargs) -> dict:
        """
        Insert document metadata into PostgreSQL following FR002 specifications.
        
        Args:
            points: List of document dictionaries containing:
                - document_id: str - unique document identifier  
                - user_id: str - user who owns the document
                - filename: str - original filename
                - file_size: int - file size in bytes
                - file_url: str - MinIO file URL
                - file_type: str - file extension (optional)
                - processing_status: str - current status (optional)
                - chunks_count: int - number of chunks (optional)
                - metadata: dict - additional metadata (optional)
        
        Returns:
            dict: Response following FR002 format with documents array and processing info
        """
        import time
        start_time = time.time()
        
        if not self._check_connection():
            return {
                'documents': [],
                'total_processed': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': 'Database connection failed'
            }
        
        documents = []
        failed_inserts = []
        
        try:
            if not self._connection:
                raise Exception("No database connection")
                
            with self._connection.cursor(cursor_factory=RealDictCursor if RealDictCursor else None) as cursor:
                for point in points:
                    try:
                        # Extract fields from input
                        document_id = point.get('document_id')
                        user_id = point.get('user_id')
                        filename = point.get('filename')
                        file_size = point.get('file_size', 0)
                        file_url = point.get('file_url')
                        file_type = point.get('file_type')
                        processing_status = point.get('processing_status', 'pending')
                        chunks_count = point.get('chunks_count', 0)
                        metadata = point.get('metadata', {})
                        
                        # Validate required fields
                        if not all([document_id, user_id, filename, file_url]):
                            failed_inserts.append({
                                'filename': filename or 'unknown',
                                'error': 'Missing required fields: document_id, user_id, filename, or file_url'
                            })
                            continue
                        
                        # Extract file type from filename if not provided
                        if not file_type and '.' in filename:
                            file_type = filename.split('.')[-1].lower()
                        
                        # Use file_url as minio_path
                        minio_path = file_url
                        
                        # Validate UUID format
                        try:
                            uuid.UUID(document_id)
                            uuid.UUID(user_id)
                        except ValueError as e:
                            failed_inserts.append({
                                'filename': filename,
                                'error': f'Invalid UUID format: {str(e)}'
                            })
                            continue
                        
                        # Insert document record
                        insert_query = """
                            INSERT INTO documents (
                                document_id, user_id, filename, file_type, file_size, 
                                minio_path, processing_status, chunks_count, metadata
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s
                            ) RETURNING *
                        """
                        
                        cursor.execute(insert_query, (
                            document_id,
                            user_id,
                            filename,
                            file_type,
                            file_size,
                            minio_path,
                            processing_status,
                            chunks_count,
                            Json(metadata) if metadata and Json else json.dumps(metadata) if metadata else None
                        ))
                        
                        # Get the inserted record
                        record = cursor.fetchone()
                        
                        # Format response according to FR002
                        documents.append({
                            'document_id': str(record['document_id']),
                            'filename': record['filename'],
                            'file_size': record['file_size'],
                            'chunks_count': record['chunks_count'],
                            'processing_status': record['processing_status'],
                            'file_url': record['minio_path']
                        })
                        
                    except Exception as e:
                        failed_inserts.append({
                            'filename': point.get('filename', 'unknown'),
                            'error': f'Insert error: {str(e)}'
                        })
                
                # Commit the transaction
                if self._connection:
                    self._connection.commit()
                
        except Exception as e:
            # Rollback on error
            if self._connection:
                self._connection.rollback()
            return {
                'documents': [],
                'total_processed': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': f'Database error: {str(e)}'
            }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        response = {
            'documents': documents,
            'total_processed': len(documents),
            'processing_time_ms': processing_time
        }
        
        if failed_inserts:
            response['failed_inserts'] = failed_inserts
        
        return response
    
    def update(self, points: List[Any], **kwargs) -> dict:
        """
        Update document metadata in PostgreSQL.
        
        Args:
            points: List of document update dictionaries containing:
                - document_id: str - document identifier
                - processing_status: str - new processing status (optional)
                - chunks_count: int - new chunks count (optional)
                - filename: str - new filename (optional)
                - metadata: dict - metadata to merge (optional)
        
        Returns:
            dict: Response with updated documents info
        """
        import time
        start_time = time.time()
        
        if not self._check_connection():
            return {
                'documents': [],
                'total_processed': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': 'Database connection failed'
            }
        
        updated_documents = []
        failed_updates = []
        
        try:
            if not self._connection:
                raise Exception("No database connection")
                
            with self._connection.cursor(cursor_factory=RealDictCursor if RealDictCursor else None) as cursor:
                for point in points:
                    try:
                        document_id = point.get('document_id')
                        
                        if not document_id:
                            failed_updates.append({
                                'document_id': 'unknown',
                                'error': 'Missing document_id for update'
                            })
                            continue
                        
                        # Build dynamic update query
                        update_fields = []
                        update_values = []
                        
                        if 'processing_status' in point:
                            update_fields.append('processing_status = %s')
                            update_values.append(point['processing_status'])
                        
                        if 'chunks_count' in point:
                            update_fields.append('chunks_count = %s')
                            update_values.append(point['chunks_count'])
                        
                        if 'filename' in point:
                            update_fields.append('filename = %s')
                            update_values.append(point['filename'])
                        
                        if 'metadata' in point:
                            # Get existing metadata first
                            cursor.execute(
                                "SELECT metadata FROM documents WHERE document_id = %s",
                                (document_id,)
                            )
                            result = cursor.fetchone()
                            if result:
                                existing_metadata = result['metadata'] or {}
                                # Merge metadata
                                merged_metadata = {**existing_metadata, **point['metadata']}
                                update_fields.append('metadata = %s')
                                update_values.append(Json(merged_metadata) if Json else json.dumps(merged_metadata))
                        
                        # Always update the updated_at timestamp
                        update_fields.append('updated_at = CURRENT_TIMESTAMP')
                        
                        if not update_fields:
                            failed_updates.append({
                                'document_id': document_id,
                                'error': 'No fields to update'
                            })
                            continue
                        
                        # Add document_id for WHERE clause
                        update_values.append(document_id)
                        
                        # Execute update
                        update_query = f"""
                            UPDATE documents 
                            SET {', '.join(update_fields)}
                            WHERE document_id = %s
                            RETURNING *
                        """
                        
                        cursor.execute(update_query, update_values)
                        record = cursor.fetchone()
                        
                        if record:
                            updated_documents.append({
                                'document_id': str(record['document_id']),
                                'filename': record['filename'],
                                'file_size': record['file_size'],
                                'chunks_count': record['chunks_count'],
                                'processing_status': record['processing_status'],
                                'file_url': record['minio_path']
                            })
                        else:
                            failed_updates.append({
                                'document_id': document_id,
                                'error': 'Document not found'
                            })
                        
                    except Exception as e:
                        failed_updates.append({
                            'document_id': point.get('document_id', 'unknown'),
                            'error': f'Update error: {str(e)}'
                        })
                
                # Commit the transaction
                if self._connection:
                    self._connection.commit()
                
        except Exception as e:
            # Rollback on error
            if self._connection:
                self._connection.rollback()
            return {
                'documents': [],
                'total_processed': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': f'Database error: {str(e)}'
            }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        response = {
            'documents': updated_documents,
            'total_processed': len(updated_documents),
            'processing_time_ms': processing_time
        }
        
        if failed_updates:
            response['failed_updates'] = failed_updates
        
        return response
    
    def delete(self, points_ids: List[str], **kwargs) -> dict:
        """
        Delete document metadata from PostgreSQL by document_id.
        
        Args:
            points_ids: List of document_ids to delete
        
        Returns:
            dict: Response with deletion results
        """
        import time
        start_time = time.time()
        
        if not self._check_connection():
            return {
                'deleted_documents': [],
                'total_deleted': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': 'Database connection failed'
            }
        
        deleted_documents = []
        failed_deletions = []
        
        if isinstance(points_ids, str):
            points_ids = [points_ids]
        
        try:
            if not self._connection:
                raise Exception("No database connection")
                
            with self._connection.cursor(cursor_factory=RealDictCursor if RealDictCursor else None) as cursor:
                for document_id in points_ids:
                    try:
                        # Get document info before deletion
                        cursor.execute(
                            "SELECT document_id, filename FROM documents WHERE document_id = %s",
                            (document_id,)
                        )
                        record = cursor.fetchone()
                        
                        if not record:
                            failed_deletions.append({
                                'document_id': document_id,
                                'error': 'Document not found'
                            })
                            continue
                        
                        # Delete the document
                        cursor.execute(
                            "DELETE FROM documents WHERE document_id = %s",
                            (document_id,)
                        )
                        
                        if cursor.rowcount > 0:
                            deleted_documents.append({
                                'document_id': document_id,
                                'filename': record['filename'],
                                'status': 'deleted'
                            })
                        else:
                            failed_deletions.append({
                                'document_id': document_id,
                                'error': 'Failed to delete document'
                            })
                        
                    except Exception as e:
                        failed_deletions.append({
                            'document_id': document_id,
                            'error': f'Delete error: {str(e)}'
                        })
                
                # Commit the transaction
                if self._connection:
                    self._connection.commit()
                
        except Exception as e:
            # Rollback on error
            if self._connection:
                self._connection.rollback()
            return {
                'deleted_documents': [],
                'total_deleted': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': f'Database error: {str(e)}'
            }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        response = {
            'deleted_documents': deleted_documents,
            'total_deleted': len(deleted_documents),
            'processing_time_ms': processing_time
        }
        
        if failed_deletions:
            response['failed_deletions'] = failed_deletions
        
        return response
    
    def search(self, **kwargs) -> dict:
        """
        Search/list documents in PostgreSQL following FR002 format.
        
        Args:
            **kwargs:
                - document_id: str - specific document ID to search for
                - user_id: str - filter by user ID
                - filename_pattern: str - pattern to match filenames (LIKE)
                - processing_status: str - filter by processing status
                - file_type: str - filter by file type
                - limit: int - maximum number of results to return
                - offset: int - number of results to skip
                - order_by: str - field to order by (default: created_at)
                - order_dir: str - order direction (asc/desc, default: desc)
        
        Returns:
            dict: Response with documents array following FR002 format
        """
        import time
        start_time = time.time()
        
        if not self._check_connection():
            return {
                'documents': [],
                'total_found': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': 'Database connection failed'
            }
        
        # Extract search parameters
        document_id = kwargs.get('document_id')
        user_id = kwargs.get('user_id')
        filename_pattern = kwargs.get('filename_pattern')
        processing_status = kwargs.get('processing_status')
        file_type = kwargs.get('file_type')
        limit = kwargs.get('limit', 100)
        offset = kwargs.get('offset', 0)
        order_by = kwargs.get('order_by', 'created_at')
        order_dir = kwargs.get('order_dir', 'desc').upper()
        
        # Validate order direction
        if order_dir not in ['ASC', 'DESC']:
            order_dir = 'DESC'
        
        documents = []
        
        try:
            if not self._connection:
                raise Exception("No database connection")
                
            with self._connection.cursor(cursor_factory=RealDictCursor if RealDictCursor else None) as cursor:
                # Build WHERE conditions
                where_conditions = []
                query_params = []
                
                if document_id:
                    where_conditions.append("document_id = %s")
                    query_params.append(document_id)
                
                if user_id:
                    where_conditions.append("user_id = %s")
                    query_params.append(user_id)
                
                if filename_pattern:
                    where_conditions.append("filename ILIKE %s")
                    query_params.append(f"%{filename_pattern}%")
                
                if processing_status:
                    where_conditions.append("processing_status = %s")
                    query_params.append(processing_status)
                
                if file_type:
                    where_conditions.append("file_type = %s")
                    query_params.append(file_type)
                
                # Build WHERE clause
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # Build the query
                query = f"""
                    SELECT document_id, user_id, filename, file_type, file_size,
                           minio_path, processing_status, chunks_count,
                           created_at, updated_at, metadata
                    FROM documents
                    {where_clause}
                    ORDER BY {order_by} {order_dir}
                    LIMIT %s OFFSET %s
                """
                
                query_params.extend([limit, offset])
                
                # Execute query
                cursor.execute(query, query_params)
                records = cursor.fetchall()
                
                # Format results
                for record in records:
                    documents.append({
                        'document_id': str(record['document_id']),
                        'user_id': str(record['user_id']),
                        'filename': record['filename'],
                        'file_type': record['file_type'],
                        'file_size': record['file_size'],
                        'chunks_count': record['chunks_count'],
                        'processing_status': record['processing_status'],
                        'file_url': record['minio_path'],
                        'created_at': record['created_at'].isoformat() if record['created_at'] else None,
                        'updated_at': record['updated_at'].isoformat() if record['updated_at'] else None,
                        'metadata': record['metadata'] or {}
                    })
                
                # Get total count for pagination
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM documents
                    {where_clause}
                """
                
                cursor.execute(count_query, query_params[:-2])  # Exclude LIMIT and OFFSET
                total_count = cursor.fetchone()['total']
                
        except Exception as e:
            logging.error(f"Error searching documents: {e}")
            return {
                'documents': [],
                'total_found': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': str(e)
            }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            'documents': documents,
            'total_found': total_count,
            'returned_count': len(documents),
            'limit': limit,
            'offset': offset,
            'processing_time_ms': processing_time
        }
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict]:
        """
        Get a specific document by ID.
        
        Args:
            document_id: Document ID to retrieve
            
        Returns:
            Document dictionary or None if not found
        """
        if not self._check_connection():
            return None
        
        try:
            if not self._connection:
                return None
                
            with self._connection.cursor(cursor_factory=RealDictCursor if RealDictCursor else None) as cursor:
                cursor.execute(
                    """
                    SELECT document_id, user_id, filename, file_type, file_size,
                           minio_path, processing_status, chunks_count,
                           created_at, updated_at, metadata
                    FROM documents
                    WHERE document_id = %s
                    """,
                    (document_id,)
                )
                
                record = cursor.fetchone()
                if record:
                    return {
                        'document_id': str(record['document_id']),
                        'user_id': str(record['user_id']),
                        'filename': record['filename'],
                        'file_type': record['file_type'],
                        'file_size': record['file_size'],
                        'chunks_count': record['chunks_count'],
                        'processing_status': record['processing_status'],
                        'file_url': record['minio_path'],
                        'created_at': record['created_at'].isoformat() if record['created_at'] else None,
                        'updated_at': record['updated_at'].isoformat() if record['updated_at'] else None,
                        'metadata': record['metadata'] or {}
                    }
                return None
                
        except Exception as e:
            logging.error(f"Error getting document {document_id}: {e}")
            return None
    
    def get_user_documents(self, user_id: str, limit: int = 100, offset: int = 0) -> Dict:
        """
        Get all documents for a specific user.
        
        Args:
            user_id: User ID to get documents for
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Dictionary with documents and pagination info
        """
        return self.search(
            user_id=user_id,
            limit=limit,
            offset=offset,
            order_by='created_at',
            order_dir='desc'
        )
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.close()
