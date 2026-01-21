import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, close_db
from app.config import get_settings
from app.logging_config import setup_logging, get_logger
from app.routers import users, channels, posts, ml, analytics, ab_testing, admin

# Configure logging
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir=os.getenv("LOG_DIR", "/var/log/ppb"),
    log_file="api.log",
)
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="Personalized Post Bot - Core API",
    description="Backend API for the Personalized Post Bot ecosystem",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for MiniApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
app.include_router(ml.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(ab_testing.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "api"}


@app.get("/health/ready")
async def readiness_check():
    """Readiness check - verifies all dependencies are available."""
    import httpx
    from app.database import async_session_maker
    from sqlalchemy import text
    
    checks = {
        "service": "api",
        "postgres": "unknown",
        "qdrant": "unknown",
    }
    all_healthy = True
    
    # Check PostgreSQL
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {str(e)[:50]}"
        all_healthy = False
    
    # Check ML Service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get("http://ml-service:8002/health/ready")
            ml_checks = res.json()
            checks["ml_service"] = ml_checks.get("status", "unknown")
            if ml_checks.get("status") != "healthy":
                all_healthy = False
    except Exception as e:
        checks["ml_service"] = f"unhealthy: {str(e)[:50]}"
        all_healthy = False
    
    checks["status"] = "healthy" if all_healthy else "degraded"
    return checks


@app.get("/health/services")
async def services_health():
    """Check health of all services (proxy for dashboard)."""
    import httpx
    import redis.asyncio as aioredis
    from app.database import async_session_maker
    from sqlalchemy import text
    
    results = {}
    
    # Check PostgreSQL
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        results["postgres"] = {"status": "healthy", "port": 5432}
    except Exception as e:
        results["postgres"] = {"status": "unhealthy", "error": str(e)[:50]}
    
    # Check Redis
    try:
        from app.config import get_settings
        settings = get_settings()
        redis_client = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await redis_client.ping()
        await redis_client.aclose()
        results["redis"] = {"status": "healthy", "port": 6379}
    except Exception as e:
        results["redis"] = {"status": "unhealthy", "error": str(e)[:50]}
    
    # Check ML Service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get("http://ml-service:8002/health/ready")
            ml_data = res.json()
            results["ml_service"] = {
                "status": ml_data.get("status", "unknown"),
                "port": 8002,
                "postgres": ml_data.get("postgres", "unknown"),
                "qdrant": ml_data.get("qdrant", "unknown")
            }
            # Also include Qdrant status from ML service
            if ml_data.get("qdrant") == "healthy":
                results["qdrant"] = {"status": "healthy", "port": 6333}
            else:
                results["qdrant"] = {"status": "unhealthy", "error": ml_data.get("qdrant", "unknown")}
    except Exception as e:
        results["ml_service"] = {"status": "unhealthy", "error": str(e)[:50]}
        results["qdrant"] = {"status": "unknown", "error": "ML service unavailable"}
    
    # Check user-bot
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get("http://user-bot:8001/health/ready")
            data = res.json()
            results["user_bot"] = {"status": data.get("status", "unknown"), "port": 8001}
    except Exception as e:
        results["user_bot"] = {"status": "unhealthy", "error": str(e)[:50]}
    
    # Check main-bot via Redis heartbeat (uses DB 1)
    try:
        redis_client = aioredis.from_url(
            "redis://redis:6379/1",
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        heartbeat = await redis_client.get("ppb:main_bot:heartbeat")
        await redis_client.aclose()
        if heartbeat:
            results["main_bot"] = {"status": "healthy", "mode": "polling"}
        else:
            results["main_bot"] = {"status": "unhealthy", "error": "no heartbeat"}
    except Exception as e:
        results["main_bot"] = {"status": "unhealthy", "error": str(e)[:50]}
    
    # Check miniapp (try both service and container names)
    miniapp_ok = False
    for host in ["miniapp", "ppb-miniapp"]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"http://{host}:80/")
                if res.status_code == 200:
                    results["miniapp"] = {"status": "healthy", "port": 8080}
                    miniapp_ok = True
                    break
        except:
            continue
    if not miniapp_ok:
        results["miniapp"] = {"status": "unknown", "note": "check localhost:8080"}
    
    # Check tunnel (cloudflared)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get("http://tunnel:8080/")  # Cloudflared metrics
            results["tunnel"] = {"status": "healthy" if res.status_code in [200, 404] else "unknown"}
    except:
        results["tunnel"] = {"status": "unknown", "note": "no HTTP endpoint"}
    
    return results


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Personalized Post Bot - Core API",
        "docs": "/docs",
        "health": "/health"
    }
