from fastapi import APIRouter

from app.api import agent, auth, boarding, health, notifications, payment, pets

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(pets.router)
api.include_router(health.router)
api.include_router(boarding.router)
api.include_router(payment.router)
api.include_router(notifications.router)
api.include_router(agent.router)
