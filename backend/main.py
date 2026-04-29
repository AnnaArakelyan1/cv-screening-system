import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from database import engine, Base, SessionLocal
from routers import auth, candidates, jobs, applications, email, users, stats, audit
from models.user import User
from models.job_report import JobReport
from utils.auth import hash_password
from config import settings

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.ADMIN_EMAIL).first():
            admin = User(
                full_name="Admin",
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                is_admin=True,
            )
            db.add(admin)
            db.commit()
    except Exception:
        pass
    finally:
        db.close()

    # Preload the embedding model at startup so background tasks don't block
    try:
        from utils.matcher import get_model
        logger.info("Preloading SentenceTransformer model...")
        get_model()
        logger.info("SentenceTransformer model ready.")
    except Exception as e:
        logger.warning(f"Model preload failed (will load on first use): {e}")

    yield

app = FastAPI(title="CV Screening System", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(applications.router, prefix="/applications", tags=["Applications"])
app.include_router(email.router, prefix="/email", tags=["Email"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(stats.router, prefix="/stats", tags=["Stats"])
app.include_router(audit.router, prefix="/audit", tags=["Audit"])

@app.get("/")
def root():
    return {"message": "CV Screening System API is running"}
