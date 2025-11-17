"""
All-Thing-Eye Backend API (MongoDB Version)

FastAPI-based REST API for team activity analytics with MongoDB
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.mongo_manager import mongo_manager
from src.utils.logger import get_logger
from backend.api.v1 import query_mongo, members_mongo, activities_mongo, projects_mongo

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler for startup and shutdown"""
    # Startup
    print("🚀 Starting All-Thing-Eye API (MongoDB)...")
    
    # Initialize configuration
    config = Config()
    app.state.config = config
    
    # Initialize MongoDB
    print("🍃 Connecting to MongoDB...")
    mongo_manager.connect_sync()
    app.state.mongo_manager = mongo_manager
    
    print("✅ API startup complete")
    
    yield
    
    # Shutdown
    logger.info("🔒 Shutting down All-Thing-Eye API...")
    mongo_manager.disconnect_sync()
    logger.info("✅ API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="All-Thing-Eye API (MongoDB)",
    description="Team Activity Analytics API with MongoDB",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)


# CORS Middleware
config = Config()
cors_config = config.get('api', {}).get('cors', {})

if cors_config.get('enabled', True):
    origins = cors_config.get('origins', 'http://localhost:3000')
    if isinstance(origins, str):
        origins = [o.strip() for o in origins.split(',')]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=cors_config.get('allow_credentials', True),
        allow_methods=cors_config.get('allow_methods', ["*"]),
        allow_headers=cors_config.get('allow_headers', ["*"]),
    )


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "All-Thing-Eye API (MongoDB)",
        "version": "0.2.0",
        "status": "running",
        "database": "MongoDB",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check MongoDB connection
        db = mongo_manager.get_database_sync()
        db.command("ping")
        
        # Get collection counts
        collections_count = len(db.list_collection_names())
        
        return {
            "status": "healthy",
            "database": "connected",
            "database_type": "MongoDB",
            "database_name": db.name,
            "collections": collections_count
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# Include API routers (MongoDB versions)
app.include_router(
    query_mongo.router,
    prefix="/api/v1/query",
    tags=["query"]
)

app.include_router(
    members_mongo.router,
    prefix="/api/v1",
    tags=["members"]
)

app.include_router(
    activities_mongo.router,
    prefix="/api/v1",
    tags=["activities"]
)

app.include_router(
    projects_mongo.router,
    prefix="/api/v1",
    tags=["projects"]
)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration
    api_config = config.get('api', {})
    host = api_config.get('host', '0.0.0.0')
    port = api_config.get('port', 8001)  # Different port to avoid conflict
    reload = api_config.get('reload', False)
    workers = api_config.get('workers', 4)
    
    logger.info(f"🚀 Starting MongoDB API server on {host}:{port}")
    
    uvicorn.run(
        "backend.main_mongo:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,
        log_level="info"
    )

