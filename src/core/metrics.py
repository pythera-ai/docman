# src/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Dict, Any
import time
import logging

# Document management metrics
DOCUMENT_OPERATIONS = Counter(
    'document_operations_total',
    'Total document operations',
    ['operation', 'database', 'status']
)

DOCUMENT_OPERATION_DURATION = Histogram(
    'document_operation_duration_seconds',
    'Document operation duration',
    ['operation', 'database'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

DOCUMENTS_PROCESSED = Histogram(
    'documents_processed_count',
    'Number of documents processed per operation',
    ['operation'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500]
)

# Database connection metrics
DATABASE_CONNECTIONS = Gauge(
    'database_connections_active',
    'Number of active database connections',
    ['database']
)

DATABASE_CONNECTION_ERRORS = Counter(
    'database_connection_errors_total',
    'Total database connection errors',
    ['database', 'error_type']
)

# Search metrics
SEARCH_OPERATIONS = Counter(
    'search_operations_total',
    'Total search operations',
    ['collection', 'status', 'user_id']
)

SEARCH_DURATION = Histogram(
    'search_duration_seconds',
    'Search operation duration',
    ['collection'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

SEARCH_RESULTS = Histogram(
    'search_results_count',
    'Number of results returned by search',
    ['collection'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500]
)

# Storage metrics
STORAGE_OPERATIONS = Counter(
    'storage_operations_total',
    'Total storage operations',
    ['operation', 'bucket', 'status']
)

STORAGE_SIZE = Gauge(
    'storage_size_bytes',
    'Total storage size in bytes',
    ['bucket']
)

FILE_UPLOAD_SIZE = Histogram(
    'file_upload_size_bytes',
    'File upload size distribution',
    buckets=[1024, 10240, 102400, 1048576, 10485760, 52428800]  # 1KB to 50MB
)

# Collection metrics
COLLECTION_INFO = Info(
    'database_collection_info',
    'Information about database collections'
)

class MetricsCollector:
    """Unified metrics collector for document management system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def record_document_operation(
        self,
        operation: str,
        database: str,
        status: str,
        duration: float,
        document_count: int = 1
    ):
        """Record document operation metrics"""
        DOCUMENT_OPERATIONS.labels(
            operation=operation,
            database=database,
            status=status
        ).inc()
        
        DOCUMENT_OPERATION_DURATION.labels(
            operation=operation,
            database=database
        ).observe(duration)
        
        DOCUMENTS_PROCESSED.labels(operation=operation).observe(document_count)
    
    def record_search_operation(
        self,
        collection: str,
        status: str,
        duration: float,
        result_count: int,
        user_id: str = "anonymous"
    ):
        """Record search operation metrics"""
        SEARCH_OPERATIONS.labels(
            collection=collection,
            status=status,
            user_id=user_id
        ).inc()
        
        SEARCH_DURATION.labels(collection=collection).observe(duration)
        SEARCH_RESULTS.labels(collection=collection).observe(result_count)
    
    def record_storage_operation(
        self,
        operation: str,
        bucket: str,
        status: str,
        file_size: int = 0
    ):
        """Record storage operation metrics"""
        STORAGE_OPERATIONS.labels(
            operation=operation,
            bucket=bucket,
            status=status
        ).inc()
        
        if file_size > 0:
            FILE_UPLOAD_SIZE.observe(file_size)
    
    def record_database_connection(self, database: str, active_connections: int):
        """Record database connection metrics"""
        DATABASE_CONNECTIONS.labels(database=database).set(active_connections)
    
    def record_database_error(self, database: str, error_type: str):
        """Record database connection errors"""
        DATABASE_CONNECTION_ERRORS.labels(
            database=database,
            error_type=error_type
        ).inc()
    
    def update_collection_info(self, database: str, collection_name: str, info: Dict[str, Any]):
        """Update collection information"""
        COLLECTION_INFO.info({
            'database': database,
            'collection': collection_name,
            'points_count': str(info.get('points_count', 0)),
            'status': info.get('status', 'unknown'),
            'last_updated': str(int(time.time()))
        })

# Global metrics collector instance
metrics = MetricsCollector()

# Context managers for automatic metrics recording
class DatabaseOperationMetrics:
    """Context manager for automatic database operation metrics"""
    
    def __init__(self, operation: str, database: str, document_count: int = 1):
        self.operation = operation
        self.database = database
        self.document_count = document_count
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            status = "success" if exc_type is None else "error"
            
            metrics.record_document_operation(
                self.operation,
                self.database,
                status,
                duration,
                self.document_count
            )

class SearchOperationMetrics:
    """Context manager for automatic search operation metrics"""
    
    def __init__(self, collection: str, user_id: str = "anonymous"):
        self.collection = collection
        self.user_id = user_id
        self.start_time = None
        self.result_count = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def set_result_count(self, count: int):
        """Set the number of results returned"""
        self.result_count = count
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            status = "success" if exc_type is None else "error"
            
            metrics.record_search_operation(
                self.collection,
                status,
                duration,
                self.result_count,
                self.user_id
            )