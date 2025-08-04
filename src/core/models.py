# src/core/models.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from uuid import UUID

# Document payload models aligned with database implementations
class DocumentPayload(BaseModel):
    """Document payload structure for Qdrant chunks"""
    document_id: str = Field(..., description="Unique document identifier")
    doc_title: str = Field("", description="Document title")
    page: int = Field(0, description="Page number")
    chunk_content: str = Field(..., description="Chunk text content")
    file_url: str = Field("", description="Document file URL")
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    @validator('document_id')
    def validate_document_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Document ID cannot be empty')
        return v.strip()
    
    @validator('chunk_content')
    def validate_chunk_content(cls, v):
        if not v or not v.strip():
            raise ValueError('Chunk content cannot be empty')
        return v.strip()

class DocumentMetadata(BaseModel):
    """Document metadata structure for PostgreSQL storage"""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    file_hash: Optional[str] = Field(None, description="File hash for duplicate detection")
    chunks_count: int = Field(0, ge=0, description="Number of chunks")
    processing_status: str = Field("uploaded", description="Processing status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class SearchFilters(BaseModel):
    """Search filters for document queries"""
    document_ids: Optional[List[str]] = Field(None, description="Filter by document IDs")
    user_ids: Optional[List[str]] = Field(None, description="Filter by user IDs")
    session_ids: Optional[List[str]] = Field(None, description="Filter by session IDs")
    pages: Optional[List[int]] = Field(None, description="Filter by page numbers")
    date_range: Optional['DateRange'] = Field(None, description="Filter by date range")
    file_types: Optional[List[str]] = Field(None, description="Filter by file types")
    
    @validator('file_types')
    def validate_file_types(cls, v):
        if v:
            allowed_types = ['pdf', 'docx', 'txt', 'md', 'rtf']
            invalid_types = [t for t in v if t.lower() not in allowed_types]
            if invalid_types:
                raise ValueError(f"Invalid file types: {invalid_types}")
        return v

class DateRange(BaseModel):
    """Date range filter"""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    
    @validator('end')
    def validate_date_range(cls, v, values):
        if v and 'start' in values and values['start'] and v < values['start']:
            raise ValueError('End date must be after start date')
        return v

class SearchParams(BaseModel):
    """Search parameters"""
    limit: int = Field(10, ge=1, le=100, description="Number of results to return")
    collection_name: str = Field("document_chunks", description="Collection to search")
    include_metadata: bool = Field(True, description="Include document metadata")

class VectorSearchRequest(BaseModel):
    """Vector search request"""
    query_vector: List[float] = Field(..., description="Query embedding vector")
    filters: Optional[SearchFilters] = None
    params: Optional[SearchParams] = None
    
    @validator('query_vector')
    def validate_vector_dimension(cls, v):
        if len(v) not in [768, 1536]:  # Common embedding dimensions
            raise ValueError(f"Vector dimension must be 768 or 1536, got {len(v)}")
        return v

class ChunkResult(BaseModel):
    """Individual chunk search result"""
    id: str = Field(..., description="Chunk identifier")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    payload: DocumentPayload = Field(..., description="Chunk payload")

class SearchResponse(BaseModel):
    """Search response"""
    status: str = Field(..., description="Response status")
    chunks: List[ChunkResult] = Field(default_factory=list, description="Search results")
    total_found: int = Field(0, description="Total number of results")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    collection_searched: str = Field(..., description="Collection that was searched")
    filters_applied: Optional[SearchFilters] = None

# Document upload models
class DocumentUploadRequest(BaseModel):
    """Document upload request"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File hash")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or not v.strip():
            raise ValueError('Filename cannot be empty')
        
        # Check file extension
        allowed_extensions = ['pdf', 'docx', 'txt', 'md', 'rtf']
        file_extension = v.lower().split('.')[-1] if '.' in v else ''
        if file_extension not in allowed_extensions:
            raise ValueError(f'File type not allowed. Allowed types: {allowed_extensions}')
        
        return v.strip()
    
    @validator('file_size')
    def validate_file_size(cls, v):
        max_size = 50 * 1024 * 1024  # 50MB
        if v > max_size:
            raise ValueError(f'File size {v} exceeds maximum limit of {max_size} bytes')
        return v

class DocumentUploadResponse(BaseModel):
    """Document upload response following FR002 format"""
    documents: List[DocumentMetadata] = Field(default_factory=list, description="Successfully uploaded documents")
    total_processed: int = Field(0, description="Total documents processed")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    failed_uploads: Optional[List[Dict[str, str]]] = Field(None, description="Failed upload details")

# Chunk insertion models
class ChunkInsertRequest(BaseModel):
    """Chunk insertion request"""
    vector: List[float] = Field(..., description="Embedding vector")
    payload: DocumentPayload = Field(..., description="Chunk payload")
    id: Optional[str] = Field(None, description="Chunk ID (generated if not provided)")

class ChunkInsertResponse(BaseModel):
    """Chunk insertion response"""
    status: str = Field(..., description="Response status")
    points_processed: int = Field(0, description="Number of points processed")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    failed_points: Optional[List[Dict[str, Any]]] = Field(None, description="Failed point details")

# Database operation response models
class DatabaseOperationResponse(BaseModel):
    """Generic database operation response"""
    status: str = Field(..., description="Operation status (success/failed)")
    message: Optional[str] = Field(None, description="Operation message")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")

class ErrorResponse(BaseModel):
    """Error response model"""
    error: bool = Field(True, description="Error flag")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Error details")

# Update forward references
SearchFilters.update_forward_refs()
DocumentPayload.update_forward_refs()
ChunkResult.update_forward_refs()