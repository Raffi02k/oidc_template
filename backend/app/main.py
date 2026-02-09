from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import models, routes, seed
from app.database import engine
import os

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

raw_origins = os.getenv("CORS_ALLOWED_ORIGINS")
if raw_origins:
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
else:
    origins = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(routes.router)

@app.on_event("startup")
def seed_on_startup():
    seed.seed_data()

@app.get("/")
def read_root():
    return {"message": "Hello World"}
