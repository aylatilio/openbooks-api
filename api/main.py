# OpenBooks API
# Purpose: Public REST API over the scraped books dataset
# Layers: Endpoints delegate data access to api/repository.py
# Swagger/OpenAPI: interactive docs at /docs
from pathlib import Path
from typing import Dict, List, Literal, Optional
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from .repository import CSVBookRepository
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# OpenAPI metadata (shown on Swagger UI)
# -----------------------------------------------------------------------------
TAGS_METADATA = [
    {"name": "health", "description": "Service health and dataset availability."},
    {"name": "books", "description": "List, retrieve and search books."},
    {"name": "categories", "description": "Available book categories."},
    {"name": "stats", "description": "Collection insights and per-category statistics."},
]

app = FastAPI(
    title="OpenBooks API",
    version="1.0.0",
    description="Public API to query books scraped from books.toscrape.com",
    license_info={
        "name": "MIT License",
        "url": "https://github.com/aylatilio/openbooks-api/blob/main/LICENSE",
    },
    contact={
        "name": "Ayla Atilio Florscuk",
        "url": "https://github.com/aylatilio",
    },
    openapi_tags=TAGS_METADATA,
)

# -----------------------------------------------------------------------------
# Models (shown in OpenAPI schemas) + examples
# -----------------------------------------------------------------------------
class Book(BaseModel):
    id: int
    title: str
    price: float
    rating: int
    availability: str
    category: str
    image_url: str
    product_url: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "title": "It's Only the Himalayas",
                "price": 45.17,
                "rating": 2,
                "availability": "In stock (19 available)",
                "category": "Travel",
                "image_url": "https://books.toscrape.com/media/cache/6d/41/....jpg",
                "product_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
            }
        }
    }


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(..., description="Service status")
    csv_exists: bool = Field(..., description="Whether the CSV file exists")
    rows: int = Field(..., ge=0, description="Row count in CSV")
    last_updated: Optional[str] = Field(None, description="CSV mtime (ISO8601)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "csv_exists": True,
                "rows": 1000,
                "last_updated": "2025-08-10T22:59:25",
            }
        }
    }


class StatsOverviewResponse(BaseModel):
    total_books: int
    avg_price: float
    ratings_distribution: Dict[str, int] = Field(
        ..., description="Keys are strings '1'..'5' (star rating)."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_books": 1000,
                "avg_price": 35.42,
                "ratings_distribution": {"1": 210, "2": 205, "3": 200, "4": 195, "5": 190},
            }
        }
    }


class CategoryStats(BaseModel):
    category: str
    count: int
    min_price: float
    max_price: float
    avg_price: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "category": "Travel",
                "count": 20,
                "min_price": 23.21,
                "max_price": 56.88,
                "avg_price": 39.45,
            }
        }
    }


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------
DATA_CSV = Path(
    os.getenv(
        "DATA_CSV",
        Path(__file__).resolve().parents[1] / "data" / "raw" / "books.csv"
    )
)

def get_repo() -> CSVBookRepository:
    """Resolve the repository (DI-friendly)."""
    return CSVBookRepository(DATA_CSV)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health probe",
    response_description="Current service status and dataset metadata.",
    response_model_exclude_none=True,
)
def health(repo: CSVBookRepository = Depends(get_repo)):
    """Returns whether the dataset is present and basic metadata about it."""
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
    """'id' is a 1-based sequential identifier derived from the CSV row order."""
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
    """Return the top-N books by rating (desc)."""
    rows = repo.top_rated(limit=limit)
    return [Book(**row) for row in rows]


@app.get(
    "/api/v1/books/price-range",
    response_model=List[Book],
    tags=["books"],
    summary="Books in a price range",
)
def price_range(
    min: float = Query(..., ge=0, description="Minimum price (inclusive)."),
    max: float = Query(..., ge=0, description="Maximum price (inclusive)."),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Return books whose price is between [min, max], inclusive, sorted by price asc."""
    rows = repo.price_range(min_price=min, max_price=max, limit=limit, offset=offset)
    return [Book(**row) for row in rows]


@app.get(
    "/api/v1/books/search",
    response_model=List[Book],
    tags=["books"],
    summary="Search by title/category",
)
def search_books(
    title: Optional[str] = Query(None, description="Case-insensitive substring on title."),
    category: Optional[str] = Query(None, description="Case-insensitive substring on category."),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """Search by optional title and/or category with pagination."""
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
    """Retrieve a single book by ID (1-based)."""
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
    """Collection-level metrics (count, price average, rating distribution)."""
    return repo.stats_overview()


@app.get(
    "/api/v1/stats/categories",
    response_model=List[CategoryStats],
    tags=["stats"],
    summary="Stats per category",
)
def stats_categories(repo: CSVBookRepository = Depends(get_repo)):
    """Per-category metrics (count and price stats), sorted by count desc."""
    return repo.stats_by_category()

# Redirect root to the interactive docs
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
