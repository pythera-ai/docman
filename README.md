# Document Management System (DocMan)

A comprehensive document management system built with FastAPI that provides document upload, processing, session management, and vector search capabilities.

## 🚀 Features

- **Document Upload & Processing**: Upload documents with automatic chunking and metadata extraction
- **Session Management**: Create and manage document sessions with user isolation
- **Chunks Management**: Process, search, and manage document chunks with vector capabilities
- **Multiple Storage Backends**: MinIO for file storage, PostgreSQL for metadata, Qdrant for vectors
- **Health Monitoring**: Built-in health checks, metrics collection, and system status monitoring
- **RESTful API**: Comprehensive API with automatic documentation and OpenAPI support
- **Administrative Tools**: Session cleanup, statistics, and management endpoints
- **Testing Suite**: Comprehensive test coverage with unit, integration, and API tests

## 🏗️ Architecture

The system is built using a microservices architecture with the following components:

- **FastAPI Application**: Core API server with async request handling
- **PostgreSQL**: Metadata and session information storage
- **MinIO**: Object storage for document files
- **Qdrant**: Vector database for semantic search (upcoming feature)
- **Docker Compose**: Containerized deployment

## 📁 Project Structure

```
docman/
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── routes/            # API route handlers
│   │   │   ├── documents.py   # Document management endpoints
│   │   │   ├── sessions.py    # Session management endpoints
│   │   │   ├── chunks.py      # Document chunks endpoints
│   │   │   └── health.py      # Health monitoring endpoints
│   │   ├── services/          # Business logic services
│   │   │   └── database_manager.py  # Unified database manager
│   │   ├── dependencies.py    # FastAPI dependencies
│   │   └── main.py           # FastAPI application entry point
│   ├── core/                  # Core application logic
│   │   ├── config.py         # Configuration management
│   │   ├── models.py         # Pydantic models
│   │   ├── exceptions.py     # Custom exceptions
│   │   ├── metrics.py        # Performance metrics
│   │   └── utils.py          # Utility functions
│   └── db/                    # Database interfaces
│       ├── interface.py      # Database interface definitions
│       ├── postgres_db.py    # PostgreSQL implementation
│       ├── minio_db.py       # MinIO implementation
│       └── qdrant_db.py      # Qdrant implementation
├── tests/                     # Comprehensive test suite
│   ├── api/                   # API endpoint tests
│   │   ├── routes/           # Route-specific tests
│   │   └── test_integration.py  # Integration tests
│   └── conftest.py           # Test configuration
├── docs/                      # Documentation
├── docker-compose.yaml        # Docker services configuration
├── Dockerfile                 # Application container
├── requirements.txt           # Python dependencies
└── setup.sh                  # Setup script
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd docman
   ```

2. **Run the setup script**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Start the services**
   ```bash
   docker-compose up -d
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Manual Setup

If you prefer manual setup:

1. **Start database services**
   ```bash
   docker-compose up -d postgres minio qdrant
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## 🔧 Configuration

The application uses environment variables for configuration. Key settings include:

### Database Configuration
- `POSTGRES_URL`: PostgreSQL connection string
- `MINIO_ENDPOINT`: MinIO server endpoint
- `MINIO_ACCESS_KEY`: MinIO access key
- `MINIO_SECRET_KEY`: MinIO secret key
- `QDRANT_URL`: Qdrant server URL

### Application Settings
- `MAX_FILE_SIZE`: Maximum upload file size (default: 50MB)
- `MAX_DOCUMENTS_PER_REQUEST`: Maximum documents per batch operation
- `ALLOWED_EXTENSIONS`: Supported file types (pdf, docx, txt, md, rtf, html)
- `ENVIRONMENT`: Application environment (development/production)
- `DEBUG`: Enable debug mode and detailed error responses

## 📚 API Documentation

### Core Endpoints

#### Document Management
- `POST /api/v1/documents/session/{session_id}/upload` - Upload document to session
- `GET /api/v1/documents/` - List all documents with filtering options
- `GET /api/v1/documents/{document_id}/download` - Download document file
- `GET /api/v1/documents/{document_id}/info` - Get document information
- `GET /api/v1/documents/{document_id}/metadata` - Get document metadata
- `PUT /api/v1/documents/{document_id}/metadata` - Update document metadata
- `DELETE /api/v1/documents/{document_id}` - Delete document
- `GET /api/v1/documents/check-duplicate/{file_hash}` - Check for duplicate documents

#### Session Management
- `POST /api/v1/sessions/` - Create new session
- `GET /api/v1/sessions/{session_id}` - Get session details
- `GET /api/v1/sessions/users/{user_id}` - Get user sessions
- `PUT /api/v1/sessions/{session_id}` - Update session (extend, modify metadata)
- `DELETE /api/v1/sessions/{session_id}` - Delete session
- `POST /api/v1/sessions/expire` - Expire old sessions
- `GET /api/v1/sessions/{session_id}/documents` - Get session documents
- `GET /api/v1/sessions/admin/stats` - Get system statistics (admin)
- `POST /api/v1/sessions/admin/cleanup` - Perform system cleanup (admin)

#### Chunks Management
- `POST /api/v1/chunks/session/{session_id}/chunks` - Upload chunks to session
- `POST /api/v1/chunks/session/{session_id}/search` - Search chunks within session
- `PUT /api/v1/chunks/session/{session_id}/chunks` - Update chunks in session
- `DELETE /api/v1/chunks/session/{session_id}/chunks` - Delete chunks from session

#### Health & Monitoring
- `GET /api/v1/health/` - Basic application health status
- `GET /api/v1/health/detailed` - Detailed health information with component status
- `GET /api/v1/health/databases` - Database connectivity status
- `GET /api/v1/health/metrics` - System metrics and performance data
- `GET /api/v1/health/status/{component}` - Individual component status

### API Documentation URLs

Once the application is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Info**: http://localhost:8000/api/v1/info
- **Root API**: http://localhost:8000/

## 🗄️ Database Schema

### PostgreSQL Tables
- **document_metadata**: Document information, metadata, and session associations
- **sessions**: User session management with expiration and metadata
- **chunks**: Document chunk information with vector embeddings support

### MinIO Buckets
- **documents**: Primary document storage bucket with versioning support

### Qdrant Collections
- **document_chunks**: Vector embeddings for semantic search and similarity matching

## 🧪 Testing

The project includes a comprehensive test suite with 90+ test cases covering all API endpoints and core functionality.

```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/api/routes/test_documents.py    # Document API tests
python -m pytest tests/api/routes/test_sessions.py     # Session API tests  
python -m pytest tests/api/routes/test_chunks.py       # Chunks API tests
python -m pytest tests/api/routes/test_health.py       # Health monitoring tests
python -m pytest tests/api/test_integration.py         # Integration tests

# Run with coverage
python -m pytest tests/ --cov=src/ --cov-report=html

# Run specific test patterns
python -m pytest tests/ -k "upload"                    # All upload-related tests
python -m pytest tests/ -v                             # Verbose output
```

### Test Categories
- **API Tests**: Complete endpoint testing with FastAPI TestClient
- **Unit Tests**: Individual component and function testing
- **Integration Tests**: Cross-service functionality and workflows
- **Health Tests**: System health and monitoring verification
- **Database Tests**: Database operations and connectivity

### Test Coverage
- ✅ **Document Management**: Upload, download, metadata, deletion
- ✅ **Session Management**: CRUD operations, expiration, user sessions
- ✅ **Chunks Management**: Upload, search, update, delete operations
- ✅ **Health Monitoring**: Health checks, metrics, component status
- ✅ **Error Handling**: Exception cases and edge conditions
- ✅ **Database Integration**: PostgreSQL, MinIO, and Qdrant operations

## 🚀 Deployment

### Docker Deployment

1. **Build the application image**
   ```bash
   docker build -t docman:latest .
   ```

2. **Deploy with Docker Compose**
   ```bash
   docker-compose up -d
   ```

### Production Considerations

- Configure proper environment variables
- Set up SSL/TLS certificates
- Configure backup strategies for databases
- Implement proper logging and monitoring
- Set up reverse proxy (nginx/traefik)

## 📊 Monitoring & Health

The application includes comprehensive monitoring and observability:

### Health Checks
- **Basic Health**: `/api/v1/health/` - Application status and uptime
- **Detailed Health**: `/api/v1/health/detailed` - Component-level health status
- **Database Health**: `/api/v1/health/databases` - Database connectivity status
- **Component Status**: `/api/v1/health/status/{component}` - Individual component monitoring

### Metrics & Monitoring
- **Performance Metrics**: Request timing, throughput, and response times
- **System Metrics**: Memory usage, disk space, and resource utilization
- **Database Metrics**: Connection pool status, query performance
- **API Metrics**: Endpoint usage statistics and error rates

### Administrative Tools
- **System Statistics**: `/api/v1/sessions/admin/stats` - Comprehensive system overview
- **Cleanup Operations**: `/api/v1/sessions/admin/cleanup` - Automated maintenance tasks
- **Session Management**: Bulk session operations and expiration handling

### Logging & Observability
- **Structured Logging**: JSON-formatted logs with request correlation
- **Error Tracking**: Comprehensive exception logging and stack traces
- **Performance Tracking**: Request timing and database operation metrics
- **Audit Logging**: User actions and system events tracking

## 🔒 Security

- **Input Validation**: Comprehensive validation using Pydantic models and FastAPI
- **File Security**: File type restrictions, size limits, and content validation
- **Database Security**: SQL injection prevention through parameterized queries and ORM
- **CORS Configuration**: Configurable CORS settings for web integration
- **Environment Security**: Environment-based configuration for sensitive credentials
- **Error Handling**: Sanitized error responses to prevent information disclosure
- **Request Validation**: Schema validation for all API endpoints
- **Session Security**: Secure session management with expiration and cleanup

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines and type hints throughout
- Write comprehensive tests for new features (maintain 90+ test coverage)
- Update documentation and API specs as needed
- Use async/await patterns for database operations
- Implement proper error handling with custom exceptions
- Add logging and metrics for new endpoints
- Follow the existing project structure and patterns

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔮 Roadmap

### Current Features (v1.0) ✅
- ✅ Document upload, storage, and management
- ✅ Session management with user isolation
- ✅ Chunks processing and management
- ✅ Health monitoring and metrics collection
- ✅ Administrative tools and cleanup operations
- ✅ Comprehensive API documentation
- ✅ Complete test suite coverage (90+ tests)
- ✅ MinIO, PostgreSQL, and Qdrant integration

### Upcoming Features (v1.1) 🔄
- 🔄 Advanced vector search implementation
- 🔄 Document text extraction and OCR
- 🔄 Advanced search filters and faceting
- 🔄 User authentication and authorization
- 🔄 API rate limiting and quotas
- 🔄 Bulk operations optimization

### Future Enhancements (v2.0) 📋
- 📋 Document versioning and history
- 📋 Advanced analytics and reporting
- 📋 Real-time notifications and webhooks
- 📋 Multi-tenant support with isolation
- 📋 Advanced caching strategies
- 📋 Machine learning-based features

## 📞 Support

For questions, issues, or contributions:

- **Issues**: [GitHub Issues](https://github.com/pythera-ai/docman/issues)
- **Documentation**: [Project Wiki](https://github.com/pythera-ai/docman/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/pythera-ai/docman/discussions)

## 🙏 Acknowledgments

- **FastAPI** for the excellent async web framework and automatic API documentation
- **Qdrant** for high-performance vector database capabilities
- **MinIO** for scalable object storage solution
- **PostgreSQL** for reliable relational data storage
- **Docker** for containerization and development environment
- **Pydantic** for data validation and serialization
- **Pytest** for comprehensive testing framework

---

*Built with ❤️ by the DocMan team*
