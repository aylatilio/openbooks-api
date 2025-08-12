# OpenBooks API
# Purpose: Public REST API over the scraped books dataset
# Layers: Endpoints delegate data access to api/repository.py
# Docs: interactive Swagger UI at /docs

from pathlib import Path
from typing import Dict, List, Literal, Optional

import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from pydantic import ConfigDict
from prometheus_fastapi_instrumentator import Instrumentator

from .repository import CSVBookRepository
from .settings import settings
from .security import (
    authenticate_admin,
    create_access_token,
    create_refresh_token,
    decode_token,
    require_admin,
)

# --------------------------- OpenAPI metadata --------------------------- #
TAGS_METADATA = [
    {"name": "health", "description": "Service health and dataset availability."},
    {"name": "books", "description": "List, retrieve and search books."},
    {"name": "categories", "description": "Available book categories."},
    {"name": "stats", "description": "Collection insights and per-category statistics."},
    {"name": "auth", "description": "JWT authentication endpoints."},
    {"name": "ml", "description": "ML-ready data and prediction placeholders."},
    {"name": "admin", "description": "Protected administrative operations."},
]

app = FastAPI(
    title="OpenBooks API",
    version="1.0.0",
    description="Public API to query books scraped from books.toscrape.com",
    license_info={
        "name": "MIT License",
        "url": "https://github.com/aylatilio/openbooks-api/blob/main/LICENSE",
    },
    contact={"name": "Ayla Atilio Florscuk", "url": "https://github.com/aylatilio"},
    openapi_tags=TAGS_METADATA,
)

# ----------------------- Structured request logging --------------------- #
logger = logging.getLogger("openbooks")
logging.basicConfig(level=logging.INFO)

@app.middleware("http")
async def log_requests(request, call_next):
    """Lightweight structured log per request + X-Request-ID header."""
    rid = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    response = await call_next(request)
    dur_ms = (time.perf_counter() - start) * 1000.0
    logger.info(
        "rid=%s method=%s path=%s status=%s duration_ms=%.2f",
        rid, request.method, request.url.path, response.status_code, dur_ms,
    )
    response.headers["X-Request-ID"] = rid
    return response

# ---------------------- Prometheus metrics endpoint --------------------- #
# Exposes /metrics (not in OpenAPI schema)
Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

# --------------------------- OpenAPI schemas ---------------------------- #
class Book(BaseModel):
    id: int
    title: str
    price: float
    rating: int
    availability: str
    category: str
    image_url: str
    product_url: str

class HealthResponse(BaseModel):
    status: Literal["ok"]
    csv_exists: bool
    rows: int = Field(..., ge=0)
    last_updated: Optional[str] = None

class StatsOverviewResponse(BaseModel):
    total_books: int
    avg_price: float
    ratings_distribution: Dict[str, int]

class CategoryStats(BaseModel):
    category: str
    count: int
    min_price: float
    max_price: float
    avg_price: float

# --- Auth models ---
class LoginRequest(BaseModel):
    username: str = Field(description="Admin username")
    password: str = Field(description="Admin password (plain)")
    # Pydantic v2
    model_config = ConfigDict(json_schema_extra={
        "example": {"username": "admin", "password": "admin123"}
    })

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str
    model_config = ConfigDict(json_schema_extra={
        "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    })

# --- ML models ---
class FeatureRow(BaseModel):
    id: int
    title: str
    price: float
    rating: int
    category: str

class PredictionIn(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[int] = None
    category: Optional[str] = None

class PredictionsRequest(BaseModel):
    items: List[PredictionIn]
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [
                {"id": 1},
                {"title": "Some Book", "price": 60.0, "rating": 5, "category": "Default"},
                {"title": "Cheap 2-star", "price": 5.0, "rating": 2, "category": "Default"}
            ]
        }
    })

class PredictionOut(BaseModel):
    id: int
    prediction: float

# ------------------------------ DI / repo ------------------------------- #
def _resolve_data_csv(path_str: str) -> Path:
    """Resolve DATA_CSV as absolute path relative to project root if needed."""
    p = Path(path_str)
    return p if p.is_absolute() else (Path(__file__).resolve().parents[1] / p)

DATA_CSV = _resolve_data_csv(settings.DATA_CSV)

def get_repo() -> CSVBookRepository:
    """Dependency provider for the repository."""
    return CSVBookRepository(DATA_CSV)

# -------------------------------- Routes -------------------------------- #
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health probe",
    response_description="Current service status and dataset metadata.",
    response_model_exclude_none=True,
)
def health(repo: CSVBookRepository = Depends(get_repo)):
    """Basic readiness + dataset visibility."""
    return repo.health()

@app.get(
    "/api/v1/books",
    response_model=List[Book],
    tags=["books"],
    summary="List books (paginated)",
    response_description="A paginated list of books.",
)
def list_books(
    limit: int = Query(100, ge=1, le=1000, description="Max number of items to return."),
    offset: int = Query(0, ge=0, description="Number of items to skip."),
    repo: CSVBookRepository = Depends(get_repo),
):
    """1-based 'id' is derived from CSV row order."""
    rows = repo.list(limit=limit, offset=offset)
    return [Book(**row) for row in rows]

@app.get(
    "/api/v1/books/top-rated",
    response_model=List[Book],
    tags=["books"],
    summary="Top rated books",
)
def top_rated(
    limit: int = Query(10, ge=1, le=100, description="How many items to return."),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Top-N by rating (desc)."""
    rows = repo.top_rated(limit=limit)
    return [Book(**row) for row in rows]

@app.get("/api/v1/books/price-range", response_model=List[Book], tags=["books"], summary="Books in a price range")
def price_range(
    min_price: float = Query(..., ge=0, description="Minimum price (inclusive).", example=20),
    max_price: float = Query(..., ge=0, description="Maximum price (inclusive).", example=30),
    limit: int = Query(100, ge=1, le=1000, example=5),
    offset: int = Query(0, ge=0, example=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Items priced within [min_price, max_price] (inclusive)."""
    rows = repo.price_range(min_price=min_price, max_price=max_price, limit=limit, offset=offset)
    return [Book(**row) for row in rows]

@app.get(
    "/api/v1/books/search",
    response_model=List[Book],
    tags=["books"],
    summary="Search by title/category",
)
def search_books(
    title: Optional[str] = Query(None, description="Case-insensitive substring on title.", example="moon"),
    category: Optional[str] = Query(None, description="Case-insensitive substring on category.", example="Travel"),
    limit: int = Query(100, ge=1, le=1000, example=5),
    offset: int = Query(0, ge=0, example=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Search by optional title/category with pagination."""
    rows = repo.search(title=title, category=category, limit=limit, offset=offset)
    return [Book(**row) for row in rows]

@app.get(
    "/api/v1/books/{book_id}",
    response_model=Book,
    tags=["books"],
    summary="Get a single book by ID",
    responses={404: {"description": "Book not found"}},
)
def get_book(book_id: int, repo: CSVBookRepository = Depends(get_repo)):
    """1-based ID access."""
    row = repo.get(book_id)
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return Book(**row)

@app.get(
    "/api/v1/categories",
    response_model=List[str],
    tags=["categories"],
    summary="List categories",
)
def list_categories(repo: CSVBookRepository = Depends(get_repo)):
    """Unique categories sorted alphabetically."""
    return repo.categories()

@app.get(
    "/api/v1/stats/overview",
    response_model=StatsOverviewResponse,
    tags=["stats"],
    summary="Global stats",
    response_model_exclude_none=True,
)
def stats_overview(repo: CSVBookRepository = Depends(get_repo)):
    """Count, average price and rating distribution."""
    return repo.stats_overview()

@app.get(
    "/api/v1/stats/categories",
    response_model=List[CategoryStats],
    tags=["stats"],
    summary="Stats per category",
)
def stats_categories(repo: CSVBookRepository = Depends(get_repo)):
    """Per-category count + price stats."""
    return repo.stats_by_category()

# ------------------------------ AUTH ------------------------------ #
@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["auth"])
def login(body: LoginRequest):
    """Return access & refresh tokens for the admin user."""
    if not authenticate_admin(body.username, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(body.username),
        refresh_token=create_refresh_token(body.username),
    )

@app.post("/api/v1/auth/refresh", response_model=TokenResponse, tags=["auth"])
def refresh(body: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    claims = decode_token(body.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    subject = claims.get("sub")
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )

# --------------------------- ADMIN (protected) --------------------------- #
@app.post("/api/v1/scraping/trigger", tags=["admin"])
def trigger_scraping(admin: str = Depends(require_admin)):
    """Protected stub for future scraping orchestration."""
    return {"status": "queued", "by": admin}

# --------------------------------- ML ----------------------------------- #
@app.get("/api/v1/ml/features", response_model=List[FeatureRow], tags=["ml"])
def ml_features(
    limit: int = Query(100, ge=1, le=10_000, example=5),
    offset: int = Query(0, ge=0, example=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Normalized columns ready for notebooks."""
    return [FeatureRow(**row) for row in repo.features(limit=limit, offset=offset)]

@app.get("/api/v1/ml/training-data", response_model=List[FeatureRow], tags=["ml"])
def ml_training_data(
    limit: int = Query(1000, ge=1, le=50_000, example=10),
    offset: int = Query(0, ge=0, example=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Large page size intended for offline downloads/training."""
    return [FeatureRow(**row) for row in repo.training_data(limit=limit, offset=offset)]

@app.post("/api/v1/ml/predictions", response_model=List[PredictionOut], tags=["ml"])
def ml_predictions(
    body: PredictionsRequest,
    repo: CSVBookRepository = Depends(get_repo),
):
    """
    Placeholder: predicts 1 if (rating >= 4) OR (price >= dataset average), else 0.
    Deterministic and stateless — demo only.
    """
    avg_price = repo.avg_price()
    out: List[PredictionOut] = []

    for i, item in enumerate(body.items):
        # Backfill from repo if only id was provided
        if item.id is not None and (item.price is None or item.rating is None):
            row = repo.get(item.id)
            if row:
                if item.price is None:
                    item.price = float(row.get("price") or 0.0)
                if item.rating is None:
                    item.rating = int(row.get("rating") or 0)

        price = float(item.price or 0.0)
        rating = int(item.rating or 0)
        pred = 1.0 if (rating >= 4 or price >= avg_price) else 0.0
        out.append(PredictionOut(id=item.id if item.id is not None else (i + 1), prediction=pred))

    return out

# ------------------------------- Root redirect -------------------------- #
@app.get("/", include_in_schema=False)
def root():
    """Redirect to Swagger UI."""
    return RedirectResponse(url="/docs")
