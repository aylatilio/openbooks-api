## OpenBooks API

FastAPI Public API to query a dataset of books collected by web scraping from books.toscrape.com.
Interactive documentation (Swagger) available at /docs.

--------------------------------------------------

## Features

- `GET /api/v1/health` — service health check and CSV metadata
- `GET /api/v1/books` — paginated listing (`limit`, `offset`)  
- `GET /api/v1/books/{id}` — details by ID (1-based)  
- `GET /api/v1/books/search` — search by `title` and/or `category` (case-insensitive)  
- `GET /api/v1/categories` — unique list of categories
- `GET /api/v1/stats/overview` — overview (total, average price, rating distribution)
- `GET /api/v1/stats/categories` — per-category metrics (count, min, max, avg)
- `GET /api/v1/books/top-rated` — top N by rating  
- `GET /api/v1/books/price-range` — books within `[min, max]`  

--------------------------------------------------

## Stack

- **Python 3.11**, **FastAPI**, **Uvicorn**
- **Pandas**, **python-dotenv**
- **VS Code REST Client**

--------------------------------------------------

## Structure

api/
  main.py         # routes and schemas
  repository.py   # CSV access and queries
data/
  raw/books.csv   # dataset
tests.http        # tests (VS Code REST Client)

--------------------------------------------------

## Environment Variables

.env.example

ENV=local
DATA_CSV=./data/raw/books.csv

--------------------------------------------------

## Running Locally

> Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

> macOS/Linux:
python3 -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -r requirements.txt

uvicorn api.main:app --reload --port 8000
> local: http://127.0.0.1:8000/docs

--------------------------------------------------

## Tests with VS Code (REST Client)

This repository includes tests.http. In VS Code, install the REST Client extension (humao.rest-client), open the file, and run each block.

Expected checks:

200 OK: /api/v1/health, /books, /books/search, /categories, /stats/*, /books/top-rated, /books/price-range

404: /api/v1/books/9999 (nonexistent ID)

307/308: / (redirects to /docs)

--------------------------------------------------

> Quick Examples (cURL)

# Health
curl -s http://127.0.0.1:8000/api/v1/health | jq

# Paginated list
curl -s "http://127.0.0.1:8000/api/v1/books?limit=5&offset=10" | jq

# Search by title
curl -s "http://127.0.0.1:8000/api/v1/books/search?title=moon&limit=5" | jq

# Top-rated
curl -s "http://127.0.0.1:8000/api/v1/books/top-rated?limit=5" | jq

# Price range
curl -s "http://127.0.0.1:8000/api/v1/books/price-range?min=20&max=30&limit=5" | jq

--------------------------------------------------

> Notes
The id field is 1-based and derives from the CSV order.
The CSV is read from DATA_CSV (default ./data/raw/books.csv).

--------------------------------------------------

## Diagram
See the diagrams in (./docs/diagrams.md).