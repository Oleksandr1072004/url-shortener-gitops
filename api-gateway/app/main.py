import json
import logging
import os
import random
import time
import string
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from . import models
from .schemas import ShortenRequest, ShortenResponse, LinkStats
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

app = FastAPI(title="URL Shortener API", version="1.0.0")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CODE_LENGTH = int(os.getenv("CODE_LENGTH", "6"))


@app.on_event("startup")
def on_startup():
    """Створюємо таблиці при старті застосунку, а не при імпорті."""
    Base.metadata.create_all(bind=engine)

def generate_code(n: int = CODE_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=n))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/shorten", response_model=ShortenResponse)
def shorten(payload: ShortenRequest, db: Session = Depends(get_db)):
    # генеруємо унікальний код
    for _ in range(10):
        code = generate_code()
        if not db.query(models.Link).filter_by(code=code).first():
            break
    else:
        raise HTTPException(500, "Could not generate unique code")

    link = models.Link(code=code, original_url=str(payload.url), clicks=0)
    db.add(link)
    db.commit()
    db.refresh(link)
    return {"code": code, "short_url": f"{BASE_URL}/{code}"}


@app.get("/stats/{code}", response_model=LinkStats)
def stats(code: str, db: Session = Depends(get_db)):
    link = db.query(models.Link).filter_by(code=code).first()
    if not link:
        raise HTTPException(404, "Not found")
    return link


@app.get("/{code}")
def redirect(code: str, db: Session = Depends(get_db)):
    link = db.query(models.Link).filter_by(code=code).first()
    if not link:
        raise HTTPException(404, "Not found")
    link.clicks += 1
    db.commit()
    return RedirectResponse(url=link.original_url)

@app.get("/version")
def version():
    return {"version": os.getenv("APP_VERSION", "dev")}

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["route"])
FAIL_RATE = float(os.getenv("FAIL_RATE", "0"))
SKIP = {"/metrics", "/health"}

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path in SKIP:
        return await call_next(request)

    if random.random() < FAIL_RATE:
        return Response(content='{"error": "injected failure"}', status_code=500)

    t0 = time.perf_counter()
    response = await call_next(request)
    dt = time.perf_counter() - t0

    route = request.scope.get("route", {}).path if request.scope.get("route") else "unknown"
    REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    LATENCY.labels(route).observe(dt)

    logging.info(json.dumps({
        "level": "error" if response.status_code >= 500 else "info",
        "msg": "request",
        "method": request.method,
        "route": route,
        "status": response.status_code,
        "duration_ms": round(dt * 1000, 1),
        "version": os.getenv("APP_VERSION", "dev"),
    }))
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
