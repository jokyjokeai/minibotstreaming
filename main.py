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

# Nouveaux routers streaming (conditionnels)
try:
    from api import streaming
    app.include_router(streaming.router, prefix="", tags=["streaming"])
    logger.info("✅ Streaming API endpoints registered")
except ImportError as e:
    logger.warning(f"⚠️ Streaming API not available: {e}")
except Exception as e:
    logger.error(f"❌ Error loading streaming API: {e}")

# Router téléchargements sécurisés (conditionnel)
try:
    from api.downloads import downloads_router
    app.include_router(downloads_router, prefix="", tags=["downloads"])
    logger.info("✅ Secure downloads API endpoints registered")
except ImportError as e:
    logger.warning(f"⚠️ Downloads API not available: {e}")
except Exception as e:
    logger.error(f"❌ Error loading downloads API: {e}")

logger.info("✅ API routers registered: /calls, /campaigns, /stats")

@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("📍 Root endpoint accessed")
    return {
        "message": "Robot d'Appels Automatique avec IA - Mode Streaming",
        "description": "Architecture temps réel avec Vosk ASR + Ollama NLP",
        "version": "2.0.0",
        "mode": "streaming",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for streaming-only architecture"""
    logger.info("🏥 Health check endpoint accessed")
    
    # Test database connection
    try:
        from sqlalchemy import text
        from database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
        logger.info("✅ Database connection healthy")
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Test streaming services
    streaming_status = "unknown"
    try:
        # Check if streaming services are available
        import config
        if config.STREAMING_MODE:
            streaming_status = "enabled"
        else:
            streaming_status = "disabled"
        logger.info(f"🌊 Streaming services: {streaming_status}")
    except Exception as e:
        logger.error(f"❌ Streaming services check failed: {e}")
        streaming_status = "error"
    
    # Test Ollama connection (optional)
    ollama_status = "unknown"
    try:
        import requests
        response = requests.get("http://localhost:11434/api/version", timeout=2)
        if response.status_code == 200:
            ollama_status = "running"
        else:
            ollama_status = "unreachable"
    except Exception:
        ollama_status = "unreachable"
    
    health_status = "healthy" if db_status == "healthy" and streaming_status == "enabled" else "unhealthy"
    logger.info(f"🏥 Overall health status: {health_status}")

    return {
        "status": health_status,
        "mode": "streaming",
        "database": db_status,
        "streaming": streaming_status,
        "ollama": ollama_status,
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🌐 Starting uvicorn server on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)