# src/core/utils.py
import hashlib
import uuid
import mimetypes
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def generate_document_id(filename: str, content: Optional[bytes] = None) -> str:
    """
    Generate a unique document ID based on filename and content.
    
    Args:
        filename: Original filename
        content: File content bytes (optional)
        
    Returns:
        str: Unique document identifier
    """
    if content:
        # Use content hash for better uniqueness
        content_hash = hashlib.sha256(content).hexdigest()
        return content_hash[:32]  # Use first 32 characters
    else:
        # Fallback to filename-based hash with timestamp
        timestamp = str(int(datetime.utcnow().timestamp() * 1000))
        combined = f"{filename}_{timestamp}"
        return hashlib.md5(combined.encode()).hexdigest()

def generate_chunk_id(document_id: str, page: int, chunk_index: int) -> str:
    """
    Generate a unique chunk ID.
    
    Args:
        document_id: Document identifier
        page: Page number
        chunk_index: Chunk index within the page
        
    Returns:
        str: Unique chunk identifier
    """
    combined = f"{document_id}_{page}_{chunk_index}"
    return hashlib.md5(combined.encode()).hexdigest()

def calculate_file_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Calculate file hash.
    
    Args:
        content: File content bytes
        algorithm: Hash algorithm (sha256, md5, sha1)
        
    Returns:
        str: File hash
    """
    if algorithm == "sha256":
        return hashlib.sha256(content).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(content).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(content).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

def detect_content_type(filename: str, content: Optional[bytes] = None) -> str:
    """
    Detect content type from filename and content.
    
    Args:
        filename: File name
        content: File content bytes (optional)
        
    Returns:
        str: MIME type
    """
    # Try to guess from filename
    content_type, _ = mimetypes.guess_type(filename)
    
    if content_type:
        return content_type
    
    # Fallback based on extension
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    
    extension_mapping = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'txt': 'text/plain',
        'md': 'text/markdown',
        'rtf': 'application/rtf'
    }
    
    return extension_mapping.get(extension, 'application/octet-stream')

def validate_file_type(filename: str, allowed_types: Optional[List[str]] = None) -> bool:
    """
    Validate if file type is allowed.
    
    Args:
        filename: File name
        allowed_types: List of allowed extensions
        
    Returns:
        bool: True if file type is allowed
    """
    if allowed_types is None:
        allowed_types = ['pdf', 'docx', 'txt', 'md', 'rtf']
    
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    return extension in allowed_types

def validate_file_size(file_size: int, max_size: Optional[int] = None) -> bool:
    """
    Validate if file size is within limits.
    
    Args:
        file_size: File size in bytes
        max_size: Maximum allowed size in bytes
        
    Returns:
        bool: True if file size is valid
    """
    if max_size is None:
        max_size = 50 * 1024 * 1024  # 50MB default
    
    return 0 < file_size <= max_size

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    size_float = float(size_bytes)
    i = 0
    while size_float >= 1024 and i < len(size_names) - 1:
        size_float /= 1024.0
        i += 1
    
    return f"{size_float:.1f} {size_names[i]}"

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    import re
    
    # Remove or replace dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty
    if not filename:
        filename = f"unnamed_{uuid.uuid4().hex[:8]}"
    
    return filename

def create_file_url(base_url: str, bucket_name: str, object_name: str) -> str:
    """
    Create a file URL for accessing stored documents.
    
    Args:
        base_url: Base URL of the storage service
        bucket_name: Storage bucket name
        object_name: Object name/key
        
    Returns:
        str: Complete file URL
    """
    base_url = base_url.rstrip('/')
    return f"{base_url}/{bucket_name}/{object_name}"

def parse_search_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate search filters.
    
    Args:
        filters: Raw filter dictionary
        
    Returns:
        Dict[str, Any]: Parsed and validated filters
    """
    parsed_filters = {}
    
    # Handle document IDs
    if 'document_ids' in filters:
        doc_ids = filters['document_ids']
        if isinstance(doc_ids, str):
            parsed_filters['document_ids'] = [doc_ids]
        elif isinstance(doc_ids, list):
            parsed_filters['document_ids'] = doc_ids
    
    # Handle user IDs
    if 'user_ids' in filters:
        user_ids = filters['user_ids']
        if isinstance(user_ids, str):
            parsed_filters['user_ids'] = [user_ids]
        elif isinstance(user_ids, list):
            parsed_filters['user_ids'] = user_ids
    
    # Handle session IDs
    if 'session_ids' in filters:
        session_ids = filters['session_ids']
        if isinstance(session_ids, str):
            parsed_filters['session_ids'] = [session_ids]
        elif isinstance(session_ids, list):
            parsed_filters['session_ids'] = session_ids
    
    # Handle pages
    if 'pages' in filters:
        pages = filters['pages']
        if isinstance(pages, int):
            parsed_filters['pages'] = [pages]
        elif isinstance(pages, list):
            parsed_filters['pages'] = pages
    
    return parsed_filters

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum chunk size in characters
        overlap: Overlap between chunks
        
    Returns:
        List[str]: List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at word boundaries
        if end < len(text):
            # Find the last space before the end
            last_space = text.rfind(' ', start, end)
            if last_space > start:
                end = last_space
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - overlap
        if start <= 0:
            start = end
    
    return chunks

def merge_metadata(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge metadata dictionaries with conflict resolution.
    
    Args:
        existing: Existing metadata
        new: New metadata to merge
        
    Returns:
        Dict[str, Any]: Merged metadata
    """
    merged = existing.copy()
    
    for key, value in new.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_metadata(merged[key], value)
        else:
            # New value overwrites existing
            merged[key] = value
    
    return merged

class Timer:
    """Simple timer utility for measuring execution time"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start the timer"""
        self.start_time = datetime.utcnow()
        return self
    
    def stop(self):
        """Stop the timer"""
        self.end_time = datetime.utcnow()
        return self
    
    def elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds"""
        if self.start_time is None:
            return 0
        
        end = self.end_time or datetime.utcnow()
        delta = end - self.start_time
        return int(delta.total_seconds() * 1000)
    
    def __enter__(self):
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
