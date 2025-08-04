# src/core/exceptions.py
from typing import Optional, Dict, Any

class DocumentManagementException(Exception):
    """Base exception for document management operations"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "DOCMAN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }

# Database connection exceptions
class DatabaseConnectionException(DocumentManagementException):
    def __init__(self, database_type: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Failed to connect to {database_type} database",
            "DATABASE_CONNECTION_ERROR",
            details or {"database_type": database_type}
        )

class QdrantConnectionException(DatabaseConnectionException):
    def __init__(self, url: Optional[str] = None):
        super().__init__(
            "Qdrant",
            {"url": url} if url else None
        )

class MinIOConnectionException(DatabaseConnectionException):
    def __init__(self, endpoint: Optional[str] = None):
        super().__init__(
            "MinIO",
            {"endpoint": endpoint} if endpoint else None
        )

class PostgresConnectionException(DatabaseConnectionException):
    def __init__(self, host: Optional[str] = None, database: Optional[str] = None):
        super().__init__(
            "PostgreSQL",
            {"host": host, "database": database} if host else None
        )

# Document processing exceptions
class DocumentProcessingException(DocumentManagementException):
    def __init__(self, message: str, document_id: Optional[str] = None):
        super().__init__(
            message,
            "DOCUMENT_PROCESSING_ERROR",
            {"document_id": document_id} if document_id else None
        )

class DocumentNotFoundException(DocumentManagementException):
    def __init__(self, document_id: str):
        super().__init__(
            f"Document '{document_id}' not found",
            "DOCUMENT_NOT_FOUND",
            {"document_id": document_id}
        )

class DocumentValidationException(DocumentManagementException):
    def __init__(self, reason: str, document_id: Optional[str] = None):
        super().__init__(
            f"Document validation failed: {reason}",
            "DOCUMENT_VALIDATION_ERROR",
            {"reason": reason, "document_id": document_id}
        )

class UnsupportedFileTypeException(DocumentManagementException):
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            f"File type '{file_type}' not supported. Allowed types: {allowed_types}",
            "UNSUPPORTED_FILE_TYPE",
            {"file_type": file_type, "allowed_types": allowed_types}
        )

class FileSizeExceededException(DocumentManagementException):
    def __init__(self, file_size: int, max_size: int):
        super().__init__(
            f"File size {file_size} bytes exceeds maximum limit of {max_size} bytes",
            "FILE_SIZE_EXCEEDED",
            {"file_size": file_size, "max_size": max_size}
        )

# Search and retrieval exceptions
class SearchException(DocumentManagementException):
    def __init__(self, message: str, query_details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "SEARCH_ERROR",
            query_details
        )

class CollectionNotFoundException(SearchException):
    def __init__(self, collection_name: str):
        super().__init__(
            f"Collection '{collection_name}' not found",
            {"collection_name": collection_name}
        )

class InvalidQueryException(SearchException):
    def __init__(self, reason: str, query_data: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Invalid query: {reason}",
            {"reason": reason, "query_data": query_data}
        )

class SearchTimeoutException(SearchException):
    def __init__(self, timeout: int):
        super().__init__(
            f"Search operation timed out after {timeout} seconds",
            {"timeout": timeout}
        )

# Storage exceptions
class StorageException(DocumentManagementException):
    def __init__(self, message: str, storage_type: str = "unknown"):
        super().__init__(
            message,
            "STORAGE_ERROR",
            {"storage_type": storage_type}
        )

class BucketNotFoundException(StorageException):
    def __init__(self, bucket_name: str):
        super().__init__(
            f"Bucket '{bucket_name}' not found",
            "MinIO"
        )
        self.details["bucket_name"] = bucket_name

class DuplicateDocumentException(DocumentManagementException):
    def __init__(self, document_id: str, existing_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Document '{document_id}' already exists",
            "DUPLICATE_DOCUMENT",
            {"document_id": document_id, "existing_info": existing_info}
        )