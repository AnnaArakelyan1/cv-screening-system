from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, candidates, jobs, applications

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CV Screening System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(applications.router, prefix="/applications", tags=["Applications"])

@app.get("/")
def root():
    return {"message": "CV Screening System API is running"}