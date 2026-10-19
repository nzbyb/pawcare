from fastapi import APIRouter

from app.api import auth, health, pets

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(pets.router)
api.include_router(health.router)
