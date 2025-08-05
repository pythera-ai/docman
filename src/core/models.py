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


class ChunkMetadata(BaseModel):
    """Chunk metadata for upload to Qdrant"""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Document identifier")
    document_title: str = Field(..., description="Document title/filename")
    chunk_text: str = Field(..., description="Chunk text content")
    vector: List[float] = Field(..., description="Embedding vector")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    page_number: Optional[int] = Field(None, description="Page number")
    section: Optional[str] = Field(None, description="Document section")


class SearchRequest(BaseModel):
    """Search request model"""
    query_vector: List[float] = Field(..., description="Query embedding vector")
    limit: Optional[int] = Field(5, description="Number of results to return")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional search filters")


class SearchResult(BaseModel):
    """Individual search result"""
    chunk_id: str = Field(..., description="Chunk identifier")
    document_id: str = Field(..., description="Document identifier")
    document_title: str = Field(..., description="Document title")
    chunk_text: str = Field(..., description="Relevant text excerpt")
    similarity_score: float = Field(..., description="Similarity score")
    source: str = Field(..., description="Source type (main|temp)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchResponse(BaseModel):
    """Search response model"""
    query_vector: List[float] = Field(..., description="Original query vector")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results")
    search_time_ms: int = Field(..., description="Search time in milliseconds")


class ChunkUploadRequest(BaseModel):
    """Request model for uploading chunks"""
    chunks: List[ChunkMetadata] = Field(..., description="List of chunks to upload")


class ChunkUploadResponse(BaseModel):
    """Response model for chunk upload"""
    status: str = Field(..., description="Upload status")
    chunks_processed: int = Field(..., description="Number of chunks processed")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    failed_chunks: Optional[List[Dict[str, Any]]] = Field(None, description="Failed chunk details")


class ChunkUpdateRequest(BaseModel):
    """Request model for updating chunks"""
    chunk_id: str = Field(..., description="Chunk ID to update")
    chunk_text: Optional[str] = Field(None, description="Updated chunk text")
    vector: Optional[List[float]] = Field(None, description="Updated embedding vector")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class ChunkDeleteRequest(BaseModel):
    """Request model for deleting chunks"""
    chunk_ids: List[str] = Field(..., description="List of chunk IDs to delete")


class ChunkOperationResponse(BaseModel):
    """Response model for chunk operations"""
    status: str = Field(..., description="Operation status")
    chunks_affected: int = Field(..., description="Number of chunks affected")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Error details if any")
