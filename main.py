from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db
from api import calls, campaigns, stats
import config
from logger_config import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Robot d'Appels Automatique avec IA",
    description="API REST pour lancer des campagnes d'appels automatisés avec transcription Whisper et analyse de sentiment",
    version="1.0.0"
)

logger.info("🚀 Initializing FastAPI application")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("✅ CORS middleware configured")

# Include routers
app.include_router(calls.router, prefix="/calls", tags=["calls"])
app.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])

logger.info("✅ API routers registered: /calls, /campaigns, /stats")

@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("📍 Root endpoint accessed")
    return {
        "message": "Robot d'Appels Automatique avec IA",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("🏥 Health check endpoint accessed")
    try:
        # Test database connection
        from sqlalchemy import text
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db_status = "healthy"
        logger.info("✅ Database connection healthy")
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        db_status = "unhealthy"

    health_status = "healthy" if db_status == "healthy" else "unhealthy"
    logger.info(f"🏥 Overall health status: {health_status}")

    return {
        "status": health_status,
        "database": db_status,
        "whisper": "loaded",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🌐 Starting uvicorn server on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)