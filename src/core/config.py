# src/core/config.py
import os
from pydantic_settings import BaseSettings
from typing import Optional

class DatabaseConfig(BaseSettings):
    """Base database configuration"""
    timeout: int = 30
    max_retries: int = 3
    connection_pool_size: int = 20
    
    class Config:
        env_prefix = "DB_"

class QdrantConfig(DatabaseConfig):
    """Qdrant vector database configuration"""
    url: Optional[str] = None
    api_key: Optional[str] = None
    
    # Collection settings aligned with our implementation
    default_collection_name: str = "document_chunks"
    vector_dimension: int = 768  # Standard embedding dimension
    distance_metric: str = "cosine"
    
    # Search settings
    default_limit: int = 10
    max_limit: int = 100
    
    class Config:
        env_prefix = "QDRANT_"

class MinIOConfig(DatabaseConfig):
    """MinIO object storage configuration"""
    endpoint: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    secure: bool = True
    
    # Storage settings
    default_bucket: str = "documents"
    base_url: str = "https://minio/bucket"
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list = ["pdf", "docx", "txt", "md", "rtf"]
    
    class Config:
        env_prefix = "MINIO_"

class PostgresConfig(DatabaseConfig):
    """PostgreSQL database configuration"""
    host: Optional[str] = None
    port: int = 5432
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Connection settings
    min_connections: int = 1
    max_connections: int = 20
    
    class Config:
        env_prefix = "POSTGRES_"

class ApplicationConfig(BaseSettings):
    """Main application configuration"""
    
    # Environment
    environment: str = "development"
    debug: bool = False
    
    # Database configurations
    qdrant: QdrantConfig = QdrantConfig()
    minio: MinIOConfig = MinIOConfig()
    postgres: PostgresConfig = PostgresConfig()
    
    # Performance settings
    max_concurrent_operations: int = 10
    cache_enabled: bool = True
    cache_ttl: int = 300
    
    # Document processing
    max_documents_per_request: int = 10
    processing_timeout: int = 300
    
    class Config:
        env_prefix = "APP_"
        case_sensitive = False

# Global configuration instance
config = ApplicationConfig()