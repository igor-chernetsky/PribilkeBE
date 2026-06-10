from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pribilka.api.router import api_router
from pribilka.config import get_settings
from pribilka.db.base import Base
from pribilka.db.schema_sync import apply_schema_patches
from pribilka.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    apply_schema_patches(engine)
    yield


app = FastAPI(
    title="Pribilka API",
    description="Capital allocation opportunity scanner. Market-scoped endpoints: /api/v1/markets/{country}/",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}
