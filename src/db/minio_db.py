import os
import logging
import json
from datetime import datetime
from typing import Optional, List, Any, Union, BinaryIO
from io import BytesIO

try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    Minio = None
    S3Error = Exception

from .interface import InterfaceDatabase


class MinioDB(InterfaceDatabase):
    """
    Object storage database using MinIO for storing and managing document files.
    Supports all types of files including documents, images, videos, etc.
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: bool = True
    ) -> None:
        if not MINIO_AVAILABLE:
            raise ImportError("MinIO package is not installed. Please install it with: pip install minio")
        self._client = self.connect_client(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        
    def connect_client(self, url, **kwargs) -> Any:
        """Connect to MinIO client"""
        if not MINIO_AVAILABLE:
            return None
            
        access_key = kwargs.get('access_key')
        secret_key = kwargs.get('secret_key')
        secure = kwargs.get('secure', True)
        
        if url is not None and access_key is not None and secret_key is not None:
            try:
                if Minio is None:
                    raise ImportError("MinIO not available")
                client = Minio(
                    endpoint=url,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=secure
                )
                # Test connection
                client.list_buckets()
                logging.info(f"Successfully connected to MinIO at {url}")
                return client
            except Exception as e:
                logging.error(f"Failed to connect to MinIO: {e}")
                return None
        else:
            logging.error("Missing required connection parameters for MinIO")
            return None
    
    def _check_client(self) -> bool:
        """Check if client is available"""
        if self._client is None:
            logging.error("MinIO client is not connected")
            return False
        return True
    
    def create_bucket(self, bucket_name: str) -> bool:
        """Create a bucket if it doesn't exist"""
        if not self._check_client():
            return False
            
        try:
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logging.info(f"Bucket '{bucket_name}' created successfully")
                return True
            else:
                logging.info(f"Bucket '{bucket_name}' already exists")
                return True
        except Exception as e:
            logging.error(f"Error creating bucket '{bucket_name}': {e}")
            return False
    
    def insert(self, points: List[Any], **kwargs) -> dict:
        """
        Insert documents into MinIO bucket following FR002 specifications.
        
        Args:
            points: List of document dictionaries containing:
                - document_id: str - unique document identifier (used as object_name)
                - file_data: bytes or file-like object
                - filename: str - original filename
                - file_size: int - file size in bytes
                - content_type: str - MIME type
                - file_hash: str - file hash for duplicate detection
        
        Returns:
            dict: Response following FR002 format with documents array and processing info
        """
        import time
        start_time = time.time()
        
        bucket_name = kwargs.get('bucket_name', 'documents')
        base_url = kwargs.get('base_url', 'https://minio/bucket')
        
        documents = []
        failed_uploads = []
        
        # Ensure bucket exists
        if not self.create_bucket(bucket_name):
            return {
                'documents': [],
                'total_processed': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'error': f'Failed to create/access bucket {bucket_name}'
            }
        
        for point in points:
            try:
                document_id = point.get('document_id')
                file_data = point.get('file_data')
                filename = point.get('filename')
                file_size = point.get('file_size', 0)
                content_type = point.get('content_type', 'application/octet-stream')
                file_hash = point.get('file_hash')
                
                if not document_id or not file_data or not filename:
                    failed_uploads.append({
                        'filename': filename or 'unknown',
                        'error': 'Missing required fields: document_id, file_data, or filename'
                    })
                    continue
                
                # Validate file extension
                allowed_extensions = ['pdf', 'docx', 'txt', 'md', 'rtf']
                file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
                if file_extension not in allowed_extensions:
                    failed_uploads.append({
                        'filename': filename,
                        'error': f'File type not allowed. Allowed types: {allowed_extensions}'
                    })
                    continue
                
                # Validate file size (50MB limit)
                max_size = 50 * 1024 * 1024  # 50MB
                if file_size > max_size:
                    failed_uploads.append({
                        'filename': filename,
                        'error': f'File size {file_size} exceeds maximum limit of {max_size} bytes'
                    })
                    continue
                
                # Convert file_data to BytesIO if it's bytes
                if isinstance(file_data, bytes):
                    file_stream = BytesIO(file_data)
                    actual_size = len(file_data)
                else:
                    file_stream = file_data
                    actual_size = file_size
                
                # Use document_id as object_name (hash string)
                object_name = document_id
                
                # Prepare minimal metadata for MinIO
                upload_metadata = {
                    'original_filename': filename,
                    'file_hash': file_hash or '',
                    'upload_time': datetime.utcnow().isoformat(),
                    'file_size': str(actual_size)
                }
                
                # Upload file to MinIO
                self._client.put_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=file_stream,
                    length=actual_size if actual_size > 0 else -1,
                    content_type=content_type,
                    metadata=upload_metadata
                )
                
                # Generate file URL
                file_url = f"{base_url}/{bucket_name}/{object_name}"
                
                # Add to successful documents
                documents.append({
                    'document_id': document_id,
                    'filename': filename,
                    'file_size': actual_size,
                    'chunks_count': 0,  # Will be updated by processing service
                    'processing_status': 'uploaded',
                    'file_url': file_url
                })
                
            except Exception as e:
                failed_uploads.append({
                    'filename': point.get('filename', 'unknown'),
                    'error': f'Upload error: {str(e)}'
                })
        
        processing_time = int((time.time() - start_time) * 1000)
        
        response = {
            'documents': documents,
            'total_processed': len(documents),
            'processing_time_ms': processing_time
        }
        
        # Include failed uploads if any
        if failed_uploads:
            response['failed_uploads'] = failed_uploads
        
        return response
    
    def update(self, points: List[Any], **kwargs) -> dict:
        """
        Update documents in MinIO bucket following FR002 specifications.
        
        Args:
            points: List of document update dictionaries containing:
                - document_id: str - document identifier (object_name)
                - file_data: bytes or file-like object (optional)
                - filename: str - new filename (optional)
                - content_type: str - new content type (optional)
        
        Returns:
            dict: Response with updated documents info
        """
        import time
        start_time = time.time()
        
        bucket_name = kwargs.get('bucket_name', 'documents')
        base_url = kwargs.get('base_url', 'https://minio/bucket')
        
        updated_documents = []
        failed_updates = []
        
        for point in points:
            try:
                document_id = point.get('document_id')
                new_file_data = point.get('file_data')
                new_filename = point.get('filename')
                new_content_type = point.get('content_type')
                
                if not document_id:
                    failed_updates.append({
                        'document_id': document_id or 'unknown',
                        'error': 'Missing document_id for update'
                    })
                    continue
                
                # Use document_id as object_name
                object_name = document_id
                
                try:
                    # Get current object metadata
                    stat = self._client.stat_object(bucket_name, object_name)
                    current_metadata = stat.metadata.copy() if stat.metadata else {}
                    
                    # Update metadata fields
                    if new_filename:
                        current_metadata['original_filename'] = new_filename
                    
                    current_metadata['last_modified'] = datetime.utcnow().isoformat()
                    
                    if new_file_data:
                        # Update with new file data
                        if isinstance(new_file_data, bytes):
                            file_stream = BytesIO(new_file_data)
                            file_size = len(new_file_data)
                        else:
                            file_stream = new_file_data
                            try:
                                file_stream.seek(0, 2)
                                file_size = file_stream.tell()
                                file_stream.seek(0)
                            except:
                                file_size = -1
                        
                        current_metadata['file_size'] = str(file_size)
                        
                        # Re-upload with new data
                        self._client.put_object(
                            bucket_name=bucket_name,
                            object_name=object_name,
                            data=file_stream,
                            length=file_size if file_size > 0 else -1,
                            content_type=new_content_type or stat.content_type,
                            metadata=current_metadata
                        )
                    else:
                        # Only metadata update
                        self._client.copy_object(
                            bucket_name=bucket_name,
                            object_name=object_name,
                            source=f"{bucket_name}/{object_name}",
                            metadata=current_metadata,
                            metadata_directive="REPLACE"
                        )
                    
                    # Generate response
                    file_url = f"{base_url}/{bucket_name}/{object_name}"
                    
                    updated_documents.append({
                        'document_id': document_id,
                        'filename': current_metadata.get('original_filename', new_filename or 'unknown'),
                        'file_size': int(current_metadata.get('file_size', 0)),
                        'chunks_count': 0,  # Will be set by processing service
                        'processing_status': 'updated',
                        'file_url': file_url
                    })
                        
                except Exception as e:
                    if getattr(e, 'code', None) == 'NoSuchKey':
                        failed_updates.append({
                            'document_id': document_id,
                            'error': f'Document {document_id} not found'
                        })
                    else:
                        failed_updates.append({
                            'document_id': document_id,
                            'error': f'Error updating document: {str(e)}'
                        })
                        
            except Exception as e:
                failed_updates.append({
                    'document_id': point.get('document_id', 'unknown'),
                    'error': f'Error processing update: {str(e)}'
                })
        
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
        Delete documents from MinIO bucket by document_id.
        
        Args:
            points_ids: List of document_ids to delete (object names)
            **kwargs: bucket_name - bucket containing the documents
            
        Returns:
            dict: Response with deletion results
        """
        import time
        start_time = time.time()
        
        bucket_name = kwargs.get('bucket_name', 'documents')
        
        deleted_documents = []
        failed_deletions = []
        
        if isinstance(points_ids, str):
            points_ids = [points_ids]
        
        for document_id in points_ids:
            try:
                # Use document_id as object_name
                object_name = document_id
                
                # Delete the object
                self._client.remove_object(bucket_name, object_name)
                
                deleted_documents.append({
                    'document_id': document_id,
                    'status': 'deleted'
                })
                    
            except Exception as e:
                if getattr(e, 'code', None) == 'NoSuchKey':
                    failed_deletions.append({
                        'document_id': document_id,
                        'error': f'Document {document_id} not found'
                    })
                else:
                    failed_deletions.append({
                        'document_id': document_id,
                        'error': f'Error deleting document: {str(e)}'
                    })
        
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
        Search/list documents in MinIO bucket following FR002 format.
        
        Args:
            **kwargs:
                - bucket_name: str - bucket to search in
                - document_id: str - specific document ID to search for
                - filename_pattern: str - pattern to match original filenames
                - include_metadata: bool - whether to include file metadata
                - max_results: int - maximum number of results to return
        
        Returns:
            dict: Response with documents array following FR002 format
        """
        import time
        start_time = time.time()
        
        bucket_name = kwargs.get('bucket_name', 'documents')
        document_id = kwargs.get('document_id')
        filename_pattern = kwargs.get('filename_pattern', '')
        include_metadata = kwargs.get('include_metadata', True)
        max_results = kwargs.get('max_results', 1000)
        base_url = kwargs.get('base_url', 'https://minio/bucket')
        
        documents = []
        count = 0
        
        try:
            # If specific document_id provided, get that object directly
            if document_id:
                try:
                    stat = self._client.stat_object(bucket_name, document_id)
                    metadata = stat.metadata or {}
                    
                    # Apply filename pattern filter if specified
                    original_filename = metadata.get('x-amz-meta-original_filename', 'unknown')
                    if filename_pattern and filename_pattern.lower() not in original_filename.lower():
                        # No match found
                        pass
                    else:
                        file_url = f"{base_url}/{bucket_name}/{document_id}"
                        
                        document_info = {
                            'document_id': document_id,
                            'filename': original_filename,
                            'file_size': stat.size,
                            'chunks_count': 0,  # Will be set by processing service
                            'processing_status': 'stored',
                            'file_url': file_url
                        }
                        
                        # Add additional metadata if requested
                        if include_metadata:
                            document_info.update({
                                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None,
                                'etag': stat.etag,
                                'content_type': stat.content_type,
                                'upload_time': metadata.get('upload_time'),
                                'file_hash': metadata.get('file_hash'),
                            })
                        
                        documents.append(document_info)
                except:
                    pass  # Document not found
            else:
                # List all objects in bucket
                objects = self._client.list_objects(
                    bucket_name=bucket_name,
                    recursive=False
                )
                
                for obj in objects:
                    if count >= max_results:
                        break
                    
                    obj_document_id = obj.object_name
                    
                    # Get metadata for filename filtering
                    metadata = {}
                    original_filename = 'unknown'
                    
                    if include_metadata or filename_pattern:
                        try:
                            stat = self._client.stat_object(bucket_name, obj.object_name)
                            metadata = stat.metadata or {}
                            original_filename = metadata.get('x-amz-meta-original_filename', 'unknown')
                        except:
                            pass
                    
                    # Apply filename pattern filter
                    if filename_pattern and filename_pattern.lower() not in original_filename.lower():
                        continue
                    
                    # Generate file URL
                    file_url = f"{base_url}/{bucket_name}/{obj.object_name}"
                    
                    document_info = {
                        'document_id': obj_document_id,
                        'filename': original_filename,
                        'file_size': obj.size,
                        'chunks_count': 0,  # Will be set by processing service
                        'processing_status': 'stored',
                        'file_url': file_url
                    }
                    
                    # Add additional metadata if requested
                    if include_metadata:
                        document_info.update({
                            'last_modified': obj.last_modified.isoformat() if obj.last_modified else None,
                            'etag': obj.etag,
                            'content_type': getattr(stat, 'content_type', None) if 'stat' in locals() else None,
                            'upload_time': metadata.get('upload_time'),
                            'file_hash': metadata.get('file_hash'),
                        })
                    
                    documents.append(document_info)
                    count += 1
                
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
            'total_found': len(documents),
            'processing_time_ms': processing_time
        }
    
    def get_file(self, document_id: str, bucket_name: str = 'documents') -> Optional[bytes]:
        """
        Download and return document content as bytes.
        
        Args:
            document_id: Document ID (object name)
            bucket_name: Bucket containing the document
            
        Returns:
            File content as bytes or None if error
        """
        try:
            response = self._client.get_object(bucket_name, document_id)
            return response.read()
        except Exception as e:
            logging.error(f"Error downloading document {document_id}: {e}")
            return None
    
    def get_document_info(self, document_id: str, bucket_name: str = 'documents') -> Optional[dict]:
        """
        Get document information including metadata following FR002 format.
        
        Args:
            document_id: Document ID (object name)
            bucket_name: Bucket containing the document
            
        Returns:
            Dictionary with document information following FR002 format or None if error
        """
        try:
            stat = self._client.stat_object(bucket_name, document_id)
            metadata = stat.metadata or {}
            
            base_url = 'https://minio/bucket'  # Should be configurable
            file_url = f"{base_url}/{bucket_name}/{document_id}"
            
            return {
                'document_id': document_id,
                'filename': metadata.get('original_filename', 'unknown'),
                'file_size': stat.size,
                'chunks_count': 0,  # Will be set by processing service
                'processing_status': 'stored',
                'file_url': file_url,
                'content_type': stat.content_type,
                'upload_time': metadata.get('upload_time'),
                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None,
                'file_hash': metadata.get('file_hash'),
                'metadata': metadata
            }
        except Exception as e:
            logging.error(f"Error getting document info for {document_id}: {e}")
            return None
    
    def check_duplicate(self, file_hash: str, bucket_name: str = 'documents') -> Optional[dict]:
        """
        Check if a document with the same hash already exists.
        
        Args:
            file_hash: Hash of the file to check
            bucket_name: Bucket to search in
            
        Returns:
            Dictionary with existing document info or None if no duplicate found
        """
        try:
            # Search all objects in bucket
            objects = self._client.list_objects(bucket_name=bucket_name, recursive=False)
            
            for obj in objects:
                try:
                    stat = self._client.stat_object(bucket_name, obj.object_name)
                    metadata = stat.metadata or {}
                    
                    if metadata.get('file_hash') == file_hash:
                        return {
                            'document_id': obj.object_name,
                            'filename': metadata.get('original_filename', 'unknown'),
                            'file_size': obj.size,
                            'upload_time': metadata.get('upload_time'),
                            'file_hash': file_hash
                        }
                except:
                    continue  # Skip objects with errors
            
            return None  # No duplicate found
        except Exception as e:
            logging.error(f"Error checking duplicate for hash {file_hash}: {e}")
            return None
    
    def delete_bucket(self, bucket_name: str, force: bool = False) -> dict:
        """
        Delete a bucket.
        
        Args:
            bucket_name: Name of the bucket to delete
            force: If True, delete all objects in bucket first
            
        Returns:
            Dictionary with operation result
        """
        try:
            if force:
                # Delete all objects in bucket first
                objects = self._client.list_objects(bucket_name, recursive=True)
                object_names = [obj.object_name for obj in objects]
                if object_names:
                    errors = self._client.remove_objects(bucket_name, object_names)
                    for error in errors:
                        logging.error(f"Error deleting object {error.object_name}: {error}")
            
            self._client.remove_bucket(bucket_name)
            return {
                'status': 'success',
                'message': f'Bucket {bucket_name} deleted successfully'
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error deleting bucket {bucket_name}: {str(e)}'
            }