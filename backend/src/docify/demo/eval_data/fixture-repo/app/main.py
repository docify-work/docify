from fastapi import FastAPI

from app.db import engine
from app.models import Base
from app.routes import auth_routes, tasks
from app.services.reminders import start_scheduler

app = FastAPI(title="Taskly")
app.include_router(auth_routes.router)
app.include_router(tasks.router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)
    start_scheduler()


@app.get("/health")
def health():
    return {"status": "ok"}
