# src/core/__init__.py
"""
Core module for document management system.

This module provides:
- Configuration management
- Exception handling
- Metrics collection
- Data models
- Utility functions
"""

from .config import (
    ApplicationConfig,
    QdrantConfig,
    MinIOConfig, 
    PostgresConfig,
    config
)

from .exceptions import (
    DocumentManagementException,
    DatabaseConnectionException,
    DocumentProcessingException,
    DocumentNotFoundException,
    DocumentValidationException,
    UnsupportedFileTypeException,
    FileSizeExceededException,
    SearchException,
    CollectionNotFoundException,
    InvalidQueryException,
    SearchTimeoutException,
    StorageException,
    BucketNotFoundException,
    DuplicateDocumentException
)

from .models import (
    DocumentPayload,
    DocumentMetadata,
    SearchRequest,
    SearchResult,
    SearchResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    ChunkInsertRequest,
    ChunkInsertResponse,
    DatabaseOperationResponse,
    ErrorResponse
)

from .metrics import (
    metrics,
    MetricsCollector,
    DatabaseOperationMetrics,
    SearchOperationMetrics
)

from .utils import (
    generate_document_id,
    generate_chunk_id,
    calculate_file_hash,
    detect_content_type,
    validate_file_type,
    validate_file_size,
    format_file_size,
    sanitize_filename,
    create_file_url,
    parse_search_filters,
    chunk_text,
    merge_metadata,
    Timer
)

__all__ = [
    # Configuration
    'ApplicationConfig',
    'QdrantConfig', 
    'MinIOConfig',
    'PostgresConfig',
    'config',
    
    # Exceptions
    'DocumentManagementException',
    'DatabaseConnectionException',
    'DocumentProcessingException',
    'DocumentNotFoundException',
    'DocumentValidationException',
    'UnsupportedFileTypeException',
    'FileSizeExceededException',
    'SearchException',
    'CollectionNotFoundException',
    'InvalidQueryException',
    'SearchTimeoutException',
    'StorageException',
    'BucketNotFoundException',
    'DuplicateDocumentException',
    
    # Models
    'DocumentPayload',
    'DocumentMetadata',
    'SearchRequest',
    'SearchResult',
    'SearchResponse',
    'DocumentUploadRequest',
    'DocumentUploadResponse',
    'ChunkInsertRequest',
    'ChunkInsertResponse',
    'DatabaseOperationResponse',
    'ErrorResponse',
    
    # Metrics
    'metrics',
    'MetricsCollector',
    'DatabaseOperationMetrics',
    'SearchOperationMetrics',
    
    # Utils
    'generate_document_id',
    'generate_chunk_id',
    'calculate_file_hash',
    'detect_content_type',
    'validate_file_type',
    'validate_file_size',
    'format_file_size',
    'sanitize_filename',
    'create_file_url',
    'parse_search_filters',
    'chunk_text',
    'merge_metadata',
    'Timer'
]