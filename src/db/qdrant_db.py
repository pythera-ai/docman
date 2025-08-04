import os
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict, Union

try:
    from qdrant_client.http import models
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    models = None
    QdrantClient = None

from .interface import InterfaceDatabase

def get_distance_mapping():
    """Get distance mapping, only if Qdrant is available"""
    if not QDRANT_AVAILABLE or models is None:
        return {}
    return {
        'euclidean': models.Distance.EUCLID,
        'dot': models.Distance.DOT, 
        'manhattan': models.Distance.MANHATTAN,
        'cosine': models.Distance.COSINE
    }


class QdrantChunksDB(InterfaceDatabase):
    """ 
    Vector database using Qdrant for storing and searching document chunks.
    Supports the payload structure:
    {
        "document_id": "uuid",
        "doc_title": "AI Base in VietNam", 
        "page": 5,
        "chunk_content": "string",
        "file_url": "https://minio/bucket/path/file.pdf",
        "user_id": "None",
        "session_id": "None"
    }
    """
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant client is not installed. Please install it with: pip install qdrant-client")
        self._client = self.connect_client(url, api_key=api_key)

    def connect_client(self, url, **kwargs) -> Any:
        """Connect to Qdrant client"""
        if not QDRANT_AVAILABLE or QdrantClient is None:
            return None
            
        api_key = kwargs.get('api_key')
        
        if url is not None and api_key is not None:
            try:
                # Cloud instance
                client = QdrantClient(url=url, api_key=api_key)
                # Test connection
                client.get_collections()
                logging.info(f"Successfully connected to Qdrant cloud at {url}")
                return client
            except Exception as e:
                logging.error(f"Failed to connect to Qdrant cloud: {e}")
                return None
        elif url is not None:
            try:
                # Local instance
                client = QdrantClient(url=url)
                # Test connection
                client.get_collections()
                logging.info(f"Successfully connected to Qdrant local at {url}")
                return client
            except Exception as e:
                logging.error(f"Failed to connect to Qdrant local: {e}")
                return None
        else:
            logging.error("Missing required connection parameters for Qdrant")
            return None
    
    def _check_client(self) -> bool:
        """Check if client is available"""
        if self._client is None:
            logging.error("Qdrant client is not connected")
            return False
        return True

    def create_collection(self, collection_name: str = "document_chunks", dimension: int = 768, distance: str = 'cosine') -> bool:
        """Create a collection if it doesn't exist"""
        if not self._check_client() or not QDRANT_AVAILABLE or models is None:
            return False
            
        try:
            distance_mapping = get_distance_mapping()
            distance_metric = distance_mapping.get(distance, distance_mapping.get('cosine'))
            
            if distance_metric is None:
                logging.error("Invalid distance metric and Qdrant models not available")
                return False
                
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=dimension, 
                    distance=distance_metric
                ),
            )
            logging.info(f"Collection '{collection_name}' created successfully")
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                logging.info(f"Collection '{collection_name}' already exists")
                return True
            logging.error(f"Error creating collection '{collection_name}': {e}")
            return False

    def insert(self, points: List[Dict[str, Any]], **kwargs) -> dict:
        """
        Insert document chunks into Qdrant collection.
        
        Args:
            points: List of dictionaries containing:
                - vectors: List[float] - embedding vector
                - payload: Dict containing document_id, doc_title, page, chunk_content, file_url, user_id, session_id
                - id: Optional[str] - point ID (will be generated if not provided)
        
        Returns:
            dict: Response with insertion results
        """
        import time
        start_time = time.time()
        
        collection_name = kwargs.get('collection_name', 'document_chunks')
        
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected',
                'points_processed': 0,
                'processing_time_ms': 0
            }
        
        # Ensure collection exists
        try:
            if not self._client.collection_exists(collection_name):
                dimension = kwargs.get('dimension', 768)
                distance = kwargs.get('distance', 'cosine')
                if not self.create_collection(collection_name, dimension, distance):
                    return {
                        'status': 'failed',
                        'message': f'Failed to create collection {collection_name}',
                        'points_processed': 0,
                        'processing_time_ms': int((time.time() - start_time) * 1000)
                    }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error checking collection: {str(e)}',
                'points_processed': 0,
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
        
        # Prepare points for insertion
        qdrant_points = []
        failed_points = []
        
        for i, point in enumerate(points):
            try:
                # Extract required fields
                vector = point.get('vector')
                payload = point.get('payload', {})
                point_id = point.get('id') or str(uuid.uuid4())
                
                if not vector:
                    failed_points.append({
                        'index': i,
                        'error': 'Missing vector field'
                    })
                    continue
                
                # Validate required payload fields
                required_fields = ['document_id', 'chunk_content']
                missing_fields = [field for field in required_fields if not payload.get(field)]
                if missing_fields:
                    failed_points.append({
                        'index': i,
                        'error': f'Missing required payload fields: {missing_fields}'
                    })
                    continue
                
                # Ensure all payload fields are present with defaults
                validated_payload = {
                    'document_id': payload.get('document_id'),
                    'doc_title': payload.get('doc_title', ''),
                    'page': payload.get('page', 0),
                    'chunk_content': payload.get('chunk_content'),
                    'file_url': payload.get('file_url', ''),
                    'user_id': payload.get('user_id'),
                    'session_id': payload.get('session_id'),
                    'created_at': datetime.utcnow().isoformat()
                }
                
                if models is None:
                    failed_points.append({
                        'index': i,
                        'error': 'Qdrant models not available'
                    })
                    continue
                
                qdrant_points.append(models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=validated_payload
                ))
                
            except Exception as e:
                failed_points.append({
                    'index': i,
                    'error': f'Error processing point: {str(e)}'
                })
        
        # Insert points
        successful_count = 0
        try:
            if qdrant_points:
                self._client.upsert(
                    collection_name=collection_name,
                    points=qdrant_points
                )
                successful_count = len(qdrant_points)
                logging.info(f"Successfully inserted {successful_count} points into {collection_name}")
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error inserting points: {str(e)}',
                'points_processed': 0,
                'failed_points': failed_points,
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        response = {
            'status': 'success',
            'points_processed': successful_count,
            'processing_time_ms': processing_time
        }
        
        if failed_points:
            response['failed_points'] = failed_points
        
        return response

    def search(self, **kwargs) -> dict:
        """
        Search for similar document chunks using vector similarity.
        
        Args:
            **kwargs:
                - query_vector: List[float] - query embedding vector
                - collection_name: str - collection to search in
                - limit: int - number of results to return
                - document_id: str - filter by specific document
                - user_id: str - filter by user
                - session_id: str - filter by session
                - page: int - filter by page number
        
        Returns:
            dict: Search results with chunks
        """
        import time
        start_time = time.time()
        
        query_vector = kwargs.get('query_vector')
        collection_name = kwargs.get('collection_name', 'document_chunks')
        limit = kwargs.get('limit', 5)
        
        if not query_vector:
            return {
                'status': 'failed',
                'message': 'Missing query_vector parameter',
                'chunks': [],
                'processing_time_ms': 0
            }
        
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected',
                'chunks': [],
                'processing_time_ms': 0
            }
        
        # Build filters
        filter_conditions = []
        
        if not QDRANT_AVAILABLE or models is None:
            return {
                'status': 'failed',
                'message': 'Qdrant models not available',
                'chunks': [],
                'processing_time_ms': 0
            }
        
        if kwargs.get('document_id'):
            filter_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=kwargs['document_id'])
                )
            )
        
        if kwargs.get('user_id'):
            filter_conditions.append(
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=kwargs['user_id'])
                )
            )
        
        if kwargs.get('session_id'):
            filter_conditions.append(
                models.FieldCondition(
                    key="session_id",
                    match=models.MatchValue(value=kwargs['session_id'])
                )
            )
        
        if kwargs.get('page') is not None:
            filter_conditions.append(
                models.FieldCondition(
                    key="page",
                    match=models.MatchValue(value=kwargs['page'])
                )
            )
        
        # Perform search
        try:
            search_filter = models.Filter(must=filter_conditions) if filter_conditions else None
            
            results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=limit,
            )
            
            # Format results
            chunks = []
            for result in results:
                chunks.append({
                    "id": str(result.id),
                    "score": result.score,
                    "payload": result.payload
                })
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                'status': 'success',
                'chunks': chunks,
                'total_found': len(chunks),
                'processing_time_ms': processing_time
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Search error: {str(e)}',
                'chunks': [],
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }

    def update(self, points: List[Dict[str, Any]], **kwargs) -> dict:
        """
        Update existing points in the collection.
        
        Args:
            points: List of dictionaries containing id, vector, and payload updates
            
        Returns:
            dict: Update results
        """
        import time
        start_time = time.time()
        
        collection_name = kwargs.get('collection_name', 'document_chunks')
        
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected',
                'points_updated': 0,
                'processing_time_ms': 0
            }
        
        updated_points = []
        failed_updates = []
        
        for i, point in enumerate(points):
            try:
                point_id = point.get('id')
                if not point_id:
                    failed_updates.append({
                        'index': i,
                        'error': 'Missing point ID'
                    })
                    continue
                
                # Prepare update data
                vector = point.get('vector')
                payload = point.get('payload', {})
                
                # Add update timestamp
                if payload:
                    payload['updated_at'] = datetime.utcnow().isoformat()
                
                if not QDRANT_AVAILABLE or models is None:
                    failed_updates.append({
                        'index': i,
                        'error': 'Qdrant models not available'
                    })
                    continue
                
                # Only create point if vector is provided
                if vector is not None:
                    qdrant_point = models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                    updated_points.append(qdrant_point)
                else:
                    # Skip updates without vectors for now
                    failed_updates.append({
                        'index': i,
                        'error': 'Vector required for update operation'
                    })
                    continue
                
            except Exception as e:
                failed_updates.append({
                    'index': i,
                    'error': f'Error processing update: {str(e)}'
                })
        
        # Perform updates
        successful_count = 0
        try:
            if updated_points:
                self._client.upsert(
                    collection_name=collection_name,
                    points=updated_points
                )
                successful_count = len(updated_points)
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error updating points: {str(e)}',
                'points_updated': 0,
                'failed_updates': failed_updates,
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
        
        processing_time = int((time.time() - start_time) * 1000)
        
        response = {
            'status': 'success',
            'points_updated': successful_count,
            'processing_time_ms': processing_time
        }
        
        if failed_updates:
            response['failed_updates'] = failed_updates
        
        return response

    def delete(self, points_ids: Union[str, List[str]], **kwargs) -> dict:
        """
        Delete points by IDs or by document_id filter.
        
        Args:
            points_ids: Point IDs to delete, or document_id for filtering
            **kwargs:
                - collection_name: str - collection name
                - by_document_id: bool - if True, treat points_ids as document_ids to filter by
        
        Returns:
            dict: Deletion results
        """
        import time
        start_time = time.time()
        
        collection_name = kwargs.get('collection_name', 'document_chunks')
        by_document_id = kwargs.get('by_document_id', False)
        
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected',
                'processing_time_ms': 0
            }
        
        if isinstance(points_ids, str):
            points_ids = [points_ids]
        
        try:
            if by_document_id:
                if not QDRANT_AVAILABLE or models is None:
                    return {
                        'status': 'failed',
                        'message': 'Qdrant models not available',
                        'processing_time_ms': int((time.time() - start_time) * 1000)
                    }
                
                # Delete by document_id filter
                deleted_count = 0
                for doc_id in points_ids:
                    self._client.delete(
                        collection_name=collection_name,
                        points_selector=models.FilterSelector(
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(
                                        key="document_id",
                                        match=models.MatchValue(value=doc_id)
                                    ),
                                ]
                            )
                        ),
                    )
                    deleted_count += 1
                
                return {
                    'status': 'success',
                    'message': f'Deleted chunks for {deleted_count} document(s)',
                    'processing_time_ms': int((time.time() - start_time) * 1000)
                }
            else:
                if not QDRANT_AVAILABLE or models is None:
                    return {
                        'status': 'failed',
                        'message': 'Qdrant models not available',
                        'processing_time_ms': int((time.time() - start_time) * 1000)
                    }
                
                # Delete by point IDs - cast to proper type
                from typing import cast, Any
                self._client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(points=cast(Any, points_ids)),
                )
                
                return {
                    'status': 'success',
                    'message': f'Deleted {len(points_ids)} point(s)',
                    'processing_time_ms': int((time.time() - start_time) * 1000)
                }
                
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error deleting points: {str(e)}',
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }

    def get_chunks_by_document_id(self, document_id: str, collection_name: str = 'document_chunks') -> dict:
        """
        Get all chunks for a specific document.
        
        Args:
            document_id: Document ID to filter by
            collection_name: Collection to search in
            
        Returns:
            dict: Document chunks
        """
        import time
        start_time = time.time()
        
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected',
                'chunks': [],
                'processing_time_ms': 0
            }
        
        try:
            if not QDRANT_AVAILABLE or models is None:
                return {
                    'status': 'failed',
                    'message': 'Qdrant models not available',
                    'chunks': [],
                    'processing_time_ms': int((time.time() - start_time) * 1000)
                }
            
            results = self._client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", 
                            match=models.MatchValue(value=document_id)
                        ),
                    ],
                ),
            )
            
            # Format results
            chunks = []
            if results[0]:  # Check if results exist
                for chunk in results[0]:
                    chunks.append({
                        "id": str(chunk.id),
                        "payload": chunk.payload,
                    })
            
            return {
                'status': 'success',
                'chunks': chunks,
                'total_found': len(chunks),
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error retrieving chunks: {str(e)}',
                'chunks': [],
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }

    def get_all_chunks(self, collection_name: str = 'document_chunks', limit: int = 100) -> dict:
        """
        Get all chunks from collection with pagination.
        
        Args:
            collection_name: Collection to retrieve from
            limit: Maximum number of chunks to retrieve
            
        Returns:
            dict: All chunks with metadata
        """
        import time
        start_time = time.time()
        
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected',
                'chunks': [],
                'processing_time_ms': 0
            }
        
        try:
            results = self._client.scroll(
                collection_name=collection_name,
                limit=limit,
            )
            
            # Format results
            chunks = []
            if results[0]:  # Check if results exist
                for chunk in results[0]:
                    chunks.append({
                        "id": str(chunk.id),
                        "payload": chunk.payload,
                    })
            
            return {
                'status': 'success',
                'chunks': chunks,
                'total_found': len(chunks),
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Error retrieving chunks: {str(e)}',
                'chunks': [],
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }

    def delete_collection(self, collection_name: str) -> dict:
        """
        Delete an entire collection.
        
        Args:
            collection_name: Name of collection to delete
            
        Returns:
            dict: Deletion result
        """
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected'
            }
        
        try:
            self._client.delete_collection(collection_name=collection_name)
            return {
                'status': 'success',
                'message': f"Collection '{collection_name}' deleted successfully"
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f"Error deleting collection '{collection_name}': {str(e)}"
            }

    def get_collection_info(self, collection_name: str = 'document_chunks') -> dict:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of collection to inspect
            
        Returns:
            dict: Collection information
        """
        if not self._check_client():
            return {
                'status': 'failed',
                'message': 'Qdrant client not connected'
            }
        
        try:
            info = self._client.get_collection(collection_name)
            return {
                'status': 'success',
                'collection_info': {
                    'points_count': info.points_count,
                    'status': info.status,
                    'vectors_count': info.vectors_count,
                    'config': {
                        'params': info.config.params.dict() if info.config.params else {},
                        'hnsw_config': info.config.hnsw_config.dict() if info.config.hnsw_config else {},
                        'optimizer_config': info.config.optimizer_config.dict() if info.config.optimizer_config else {}
                    }
                }
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f"Error getting collection info: {str(e)}"
            }