import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth_org, customers, program
from app.core.config import get_settings
from app.core.llm import llm_configured
from app.core.logging import setup_logging

setup_logging()
log = logging.getLogger("api")
s = get_settings()
app = FastAPI(title="LoyaltyIQ API", version="1.0.0",
              description="Multi-tenant loyalty SaaS: points engine, RFM/K-means segmentation, reward recommendations, "
                          "AI campaign builder with human approval, analytics.")
app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins.split(","), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def access_log(request: Request, call_next):
    t = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        log.exception("unhandled", extra={"path": request.url.path, "method": request.method})
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    log.info("request", extra={"path": request.url.path, "method": request.method, "status": resp.status_code,
                               "duration_ms": round((time.perf_counter() - t) * 1000, 1)})
    return resp


for r in (auth_org.router, customers.router, program.router):
    app.include_router(r)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "llm_configured": llm_configured()}
