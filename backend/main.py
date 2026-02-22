"""
All-Thing-Eye Backend API (MongoDB Version)

FastAPI-based REST API for team activity analytics with MongoDB
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager
from src.utils.logger import get_logger
from src.scheduler.slack_scheduler import SlackScheduler
from backend.api.v1 import query_mongo, members_mongo, activities_mongo, projects_mongo, projects_management, exports_mongo, database_mongo, auth, oauth, tenants, stats_mongo, notion_export_mongo, ai_processed, custom_export, ai_proxy, mcp_api, mcp_agent, slack_bot, notion_diff, reports, weekly_output_schedules, support_bot, onboarding

logger = get_logger(__name__)

# Global mongo_manager instance
mongo_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler for startup and shutdown"""
    global mongo_manager
    
    # Startup
    print("🚀 Starting All-Thing-Eye API (MongoDB)...")
    
    # Initialize configuration
    config = Config()
    app.state.config = config
    
    # Initialize MongoDB
    print("🍃 Connecting to MongoDB...")
    mongo_config = {
        'uri': config.get('mongodb.uri', os.getenv('MONGODB_URI', 'mongodb://localhost:27017')),
        'database': config.get('mongodb.database', os.getenv('MONGODB_DATABASE', 'all_thing_eye'))
    }
    mongo_manager = get_mongo_manager(mongo_config)
    mongo_manager.connect_async()  # This is synchronous despite the name
    app.state.mongo_manager = mongo_manager
    
    # Initialize Slack Scheduler
    print("⏰ Initializing Slack Scheduler...")
    slack_scheduler = SlackScheduler(mongo_manager)
    await slack_scheduler.start()
    app.state.slack_scheduler = slack_scheduler
    
    print("✅ API startup complete")
    
    yield
    
    # Shutdown
    logger.info("🔒 Shutting down All-Thing-Eye API...")
    mongo_manager.close()
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


# CORS Middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=False,  # Must be False when allow_origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
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
        db = mongo_manager.db
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


@app.get("/test/commits")
async def test_commits_query():
    """Simple test endpoint to check MongoDB commit aggregation"""
    try:
        db = mongo_manager.get_database_async()
        commits_col = db['github_commits']
        
        # Aggregation: Count commits by author
        pipeline = [
            {"$group": {"_id": "$author_login", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        
        cursor = commits_col.aggregate(pipeline)
        results = await cursor.to_list(length=10)
        
        return {
            "status": "success",
            "data": results,
            "total": len(results)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Include API routers (MongoDB versions)

# Authentication (no JWT required)
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["authentication"]
)

# OAuth Authentication (Google & GitHub)
app.include_router(
    oauth.router,
    prefix="/api/v1/oauth",
    tags=["oauth"]
)

# Multi-Tenant Management
app.include_router(
    tenants.router,
    prefix="/api/v1/tenants",
    tags=["tenants"]
)

# Protected routes (JWT required)
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

app.include_router(
    projects_management.router,
    prefix="/api/v1/projects-management",
    tags=["projects-management"]
)

app.include_router(
    exports_mongo.router,
    prefix="/api/v1/exports",
    tags=["exports"]
)

# Database viewer routes
app.include_router(
    database_mongo.router,
    prefix="/api/v1/database",
    tags=["database"]
)

# Unified statistics routes
app.include_router(
    stats_mongo.router,
    prefix="/api/v1/stats",
    tags=["statistics"]
)

# Notion export routes
app.include_router(
    notion_export_mongo.router,
    prefix="/api/v1",
    tags=["notion-export"]
)

# AI Processed data routes (Gemini summaries, translations)
app.include_router(
    ai_processed.router,
    prefix="/api/v1",
    tags=["ai-processed"]
)

# Custom Export routes
app.include_router(
    custom_export.router,
    prefix="/api/v1",
    tags=["custom-export"]
)

# Reports routes (Biweekly report generation)
app.include_router(
    reports.router,
    prefix="/api/v1/reports",
    tags=["reports"]
)

# AI Proxy routes (proxies to Tokamak AI API)
app.include_router(
    ai_proxy.router,
    prefix="/api/v1",
    tags=["ai-proxy"]
)

# MCP API routes (Model Context Protocol HTTP wrapper)
app.include_router(
    mcp_api.router,
    prefix="/api/v1",
    tags=["mcp"]
)

# MCP Agent routes (True Function Calling Agent)
app.include_router(
    mcp_agent.router,
    prefix="/api/v1",
    tags=["mcp-agent"]
)

# Slack Bot routes
app.include_router(
    slack_bot.router,
    prefix="/api/v1/slack",
    tags=["slack-bot"]
)

# Notion Diff routes (granular content tracking)
app.include_router(
    notion_diff.router,
    prefix="/api/v1",
    tags=["notion-diff"]
)

# Weekly Output Schedules
app.include_router(
    weekly_output_schedules.router,
    prefix="/api/v1/weekly-output",
    tags=["weekly-output"]
)

# Support Bot (HTTP Events API for Slack)
app.include_router(
    support_bot.router,
    prefix="/api/v1/support",
    tags=["support-bot"]
)

# Onboarding (Welcome message via Slack DM)
app.include_router(
    onboarding.router,
    prefix="/api/v1/onboarding",
    tags=["onboarding"]
)

# GraphQL endpoint
try:
    from strawberry.fastapi import GraphQLRouter
    from backend.graphql.schema import schema
    from backend.graphql.dataloaders import create_dataloaders
    
    def get_graphql_context():
        """Create GraphQL context with database and dataloaders"""
        db = mongo_manager.async_db
        return {
            'db': db,
            'config': app.state.config,
            'dataloaders': create_dataloaders(db),
        }
    
    graphql_app = GraphQLRouter(
        schema,
        context_getter=get_graphql_context
    )
    app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])
    logger.info("✅ GraphQL endpoint enabled at /graphql")
except ImportError as e:
    logger.warning("⚠️  Strawberry GraphQL not installed. GraphQL endpoint disabled.")
    logger.warning(f"   Error: {e}")
    logger.warning("   Install with: pip install strawberry-graphql[fastapi]")
except Exception as e:
    logger.error(f"❌ Failed to initialize GraphQL endpoint: {e}")
    logger.error(f"   Error type: {type(e).__name__}")
    import traceback
    logger.error(f"   Traceback: {traceback.format_exc()}")


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
    
    logger.info(f"🚀 Starting API server on {host}:{port}")
    
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,
        log_level="info"
    )

