"""
All-Thing-Eye Backend API

FastAPI-based REST API for team activity analytics
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
from src.core.database import DatabaseManager
from src.utils.logger import get_logger
from backend.api.v1 import members, activities, projects, exports, query

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler for startup and shutdown"""
    # Startup
    print("🚀 Starting All-Thing-Eye API...")
    
    # Initialize configuration
    config = Config()
    app.state.config = config
    
    # Initialize database
    main_db_url = config.get('database', {}).get(
        'main_db', 
        'sqlite:///data/databases/main.db'
    )
    db_manager = DatabaseManager(main_db_url)
    app.state.db_manager = db_manager
    
    # Register source databases
    print("🚀 Starting database registration...")
    for source in ['github', 'slack', 'google_drive', 'notion']:
        try:
            # Construct database URL for each source
            source_db_url = f"sqlite:///data/databases/{source}.db"
            print(f"   📂 Attempting to register {source} from {source_db_url}")
            db_manager.register_existing_source_database(source, source_db_url)
            print(f"   ✅ Registered {source} database")
        except Exception as e:
            print(f"   ⚠️  Could not register {source} database: {e}")
            import traceback
            print(traceback.format_exc())
    
    print("✅ API startup complete")
    
    yield
    
    # Shutdown
    logger.info("🔒 Shutting down All-Thing-Eye API...")
    db_manager.close_all()
    logger.info("✅ API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="All-Thing-Eye API",
    description="Team Activity Analytics API",
    version="0.1.0",
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
        "name": "All-Thing-Eye API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/K8s"""
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0"
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_manager = app.state.db_manager
        with db_manager.get_connection() as conn:
            conn.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# Include API routers
app.include_router(
    members.router,
    prefix="/api/v1",
    tags=["members"]
)

app.include_router(
    activities.router,
    prefix="/api/v1",
    tags=["activities"]
)

app.include_router(
    projects.router,
    prefix="/api/v1",
    tags=["projects"]
)

app.include_router(
    exports.router,
    prefix="/api/v1/exports",
    tags=["exports"]
)

app.include_router(
    query.router,
    prefix="/api/v1/query",
    tags=["query"]
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
    port = api_config.get('port', 8000)
    reload = api_config.get('reload', False)
    workers = api_config.get('workers', 4)
    
    logger.info(f"🚀 Starting server on {host}:{port}")
    
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,
        log_level="info"
    )

