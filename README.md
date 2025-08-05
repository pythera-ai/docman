# Document Management System (DocMan)

A comprehensive document management system built with FastAPI that provides document upload, processing, session management, and vector search capabilities.

## 🚀 Features

- **Document Upload & Processing**: Upload documents with automatic chunking and metadata extraction
- **Session Management**: Create and manage document sessions with user isolation
- **Vector Search**: Document search capabilities using Qdrant vector database (planned)
- **Multiple Storage Backends**: MinIO for file storage, PostgreSQL for metadata, Qdrant for vectors
- **Health Monitoring**: Built-in health checks and metrics collection
- **RESTful API**: Comprehensive API with automatic documentation
- **Administrative Tools**: Session cleanup, statistics, and management endpoints

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
│   │   │   ├── management.py  # Session and admin endpoints
│   │   │   ├── search.py      # Search endpoints
│   │   │   └── health.py      # Health check endpoints
│   │   ├── services/          # Business logic services
│   │   └── main.py           # FastAPI application entry point
│   ├── core/                  # Core application logic
│   │   ├── config.py         # Configuration management
│   │   ├── models.py         # Pydantic models
│   │   ├── exceptions.py     # Custom exceptions
│   │   └── utils.py          # Utility functions
│   └── db/                    # Database interfaces
│       ├── interface.py      # Database interface definitions
│       ├── postgres_db.py    # PostgreSQL implementation
│       ├── minio_db.py       # MinIO implementation
│       └── qdrant_db.py      # Qdrant implementation
├── tests/                     # Test suite
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
- `ALLOWED_EXTENSIONS`: Supported file types (pdf, docx, txt, md, rtf)
- `ENVIRONMENT`: Application environment (development/production)

## 📚 API Documentation

### Core Endpoints

#### Document Management
- `POST /documents/session/{session_id}/upload` - Upload document to session
- `POST /documents/session/{session_id}/process` - Process document into chunks
- `GET /documents/session/{session_id}/documents` - List session documents
- `GET /documents/{document_id}/download` - Download document
- `DELETE /documents/{document_id}` - Delete document

#### Session Management
- `POST /management/sessions` - Create new session
- `GET /management/sessions/{session_id}` - Get session details
- `PUT /management/sessions/{session_id}` - Update session
- `DELETE /management/sessions/{session_id}` - Delete session
- `GET /management/users/{user_id}/sessions` - Get user sessions

#### Search (Planned)
- `POST /search/session/{session_id}/search` - Search within session
- `POST /search/search` - Global search across documents

#### Health & Monitoring
- `GET /health` - Application health status
- `GET /health/detailed` - Detailed health information
- `GET /management/stats` - System statistics

### API Documentation URLs

Once the application is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Info**: http://localhost:8000/api/v1/info

## 🗄️ Database Schema

### PostgreSQL Tables
- **document_metadata**: Document information and metadata
- **sessions**: User session management
- **chunks**: Document chunk information

### MinIO Buckets
- **documents**: Primary document storage bucket

### Qdrant Collections
- **document_chunks**: Vector embeddings for semantic search

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
python -m pytest tests/

# Run specific test files
python -m pytest tests/test_document_management.py
python -m pytest tests/test_session_management.py
python -m pytest tests/test_health_checks.py

# Run with coverage
python -m pytest tests/ --cov=src/
```

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Database and service integration
- **API Tests**: Endpoint functionality testing
- **Health Tests**: System health verification

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

The application includes built-in monitoring:

- **Health Checks**: Database connectivity and service status
- **Metrics Collection**: Request timing and system metrics
- **Logging**: Structured logging with configurable levels
- **Administrative Endpoints**: System statistics and cleanup tools

## 🔒 Security

- Input validation using Pydantic models
- File type restrictions and size limits
- SQL injection prevention through parameterized queries
- CORS configuration for web integration
- Environment-based configuration for sensitive data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests for new features
- Update documentation as needed
- Use type hints throughout the codebase

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔮 Roadmap

### Current Features (v1.0)
- ✅ Document upload and storage
- ✅ Session management
- ✅ Health monitoring
- ✅ Administrative tools

### Upcoming Features (v1.1)
- 🔄 Vector search implementation
- 🔄 Document text extraction
- 🔄 Advanced search filters
- 🔄 User authentication

### Future Enhancements (v2.0)
- 📋 Document versioning
- 📋 Advanced analytics
- 📋 Real-time notifications
- 📋 Multi-tenant support

## 📞 Support

For questions, issues, or contributions:

- **Issues**: [GitHub Issues](https://github.com/pythera-ai/docman/issues)
- **Documentation**: [Project Wiki](https://github.com/pythera-ai/docman/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/pythera-ai/docman/discussions)

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- Qdrant for vector database capabilities
- MinIO for object storage
- PostgreSQL for reliable data storage
- Docker for containerization support

---

*Built with ❤️ by the DocMan team*
