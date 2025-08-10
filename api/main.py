# OpenBooks API
# Purpose: Expose a public REST API for the scraped books dataset
# Layers: Endpoints delegate data access to the Repository (api/repository.py)
# Swagger/OpenAPI: available at /docs

# FastAPI entrypoint

from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

from .repository import CSVBookRepository  # OOP: data-access layer

# Path to the CSV produced by the scraper
DATA_CSV = Path(__file__).resolve().parents[1] / "data" / "raw" / "books.csv"

# API metadata also powers the Swagger UI at /docs
app = FastAPI(
    title="OpenBooks API",
    version="1.0.0",
    description="Public API to query books scraped from books.toscrape.com",
)

# Pydantic model describing the response schema for a book item
class Book(BaseModel):
    id: int
    title: str
    price: float
    rating: int
    availability: str
    category: str
    image_url: str
    product_url: str

# Dependency provider (FastAPI DI): easy to swap for a Fake/DB repository in tests
def get_repo() -> CSVBookRepository:
    return CSVBookRepository(DATA_CSV)

# ---------- Core endpoints ----------

@app.get("/api/v1/health")
def health(repo: CSVBookRepository = Depends(get_repo)):
    """
    Health/status endpoint exposing dataset availability and metadata.
    """
    return repo.health()

@app.get("/api/v1/books", response_model=List[Book])
def list_books(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """
    Paginated listing of books. 'id' is a 1-based sequential identifier.
    """
    rows = repo.list(limit=limit, offset=offset)
    return [Book(**row) for row in rows]

@app.get("/api/v1/books/search", response_model=List[Book])
def search_books(
    title: Optional[str] = Query(None, description="Case-insensitive substring"),
    category: Optional[str] = Query(None, description="Case-insensitive substring"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: CSVBookRepository = Depends(get_repo),
):
    """
    Search by optional 'title' and/or 'category' (case-insensitive), with pagination.
    """
    rows = repo.search(title=title, category=category, limit=limit, offset=offset)
    return [Book(**row) for row in rows]

@app.get("/api/v1/books/{book_id}", response_model=Book)
def get_book(book_id: int, repo: CSVBookRepository = Depends(get_repo)):
    """
    Retrieve a single book by id (1-based).
    """
    row = repo.get(book_id)
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return Book(**row)

@app.get("/api/v1/categories", response_model=List[str])
def list_categories(repo: CSVBookRepository = Depends(get_repo)):
    """
    Unique categories sorted alphabetically.
    """
    return repo.categories()

# ---------- Stats/insights endpoints (optional but recommended) ----------

@app.get("/api/v1/stats/overview")
def stats_overview(repo: CSVBookRepository = Depends(get_repo)):
    """
    High-level metrics: total books, categories count, avg/min/max price, rating distribution.
    """
    return repo.stats_overview()

@app.get("/api/v1/stats/categories")
def stats_categories(repo: CSVBookRepository = Depends(get_repo)):
    """
    Category-level metrics (count, avg/min/max price), sorted by count desc.
    """
    return repo.stats_by_category()
