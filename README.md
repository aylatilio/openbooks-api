## OpenBooks API

API pública em FastAPI para consultar um dataset de livros coletado via raspagem (web scraping) de books.toscrape.com.
A documentação interativa (Swagger) está disponível em /docs.

--------------------------------------------------

## Funcionalidades

- `GET /api/v1/health` — health check do serviço e metadados do CSV  
- `GET /api/v1/books` — listagem paginada (`limit`, `offset`)  
- `GET /api/v1/books/{id}` — detalhes por ID (1-based)  
- `GET /api/v1/books/search` — busca por `title` e/ou `category` (case-insensitive)  
- `GET /api/v1/categories` — lista única de categorias  
- `GET /api/v1/stats/overview` — visão geral (total, média de preço, distribuição de ratings)  
- `GET /api/v1/stats/categories` — métricas por categoria (count, min, max, avg)  
- `GET /api/v1/books/top-rated` — top N por rating  
- `GET /api/v1/books/price-range` — livros na faixa `[min, max]`  

--------------------------------------------------

## Stack

- **Python 3.11**, **FastAPI**, **Uvicorn**
- **Pandas**, **python-dotenv**
- **VS Code REST Client**

--------------------------------------------------

## Estrutura

api/
  main.py         # rotas e schemas
  repository.py   # acesso ao CSV e consultas
data/
  raw/books.csv   # dataset
tests.http        # testes (VS Code REST Client)

--------------------------------------------------

## Variáveis de Ambiente

.env.example

ENV=local
DATA_CSV=./data/raw/books.csv

--------------------------------------------------

## Rodando Localmente

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

## Testes com VS Code (REST Client)

Este repositório inclui tests.http. No VS Code, instale a extensão REST Client (humao.rest-client), abra o arquivo e execute os blocos.

Checks esperados:

200 OK: /api/v1/health, /books, /books/search, /categories, /stats/*, /books/top-rated, /books/price-range

404: /api/v1/books/9999 (ID inexistente)

307/308: / (redireciona para /docs)

--------------------------------------------------

> Exemplos Rápidos (cURL)

# Health
curl -s http://127.0.0.1:8000/api/v1/health | jq

# Lista paginada
curl -s "http://127.0.0.1:8000/api/v1/books?limit=5&offset=10" | jq

# Busca por título
curl -s "http://127.0.0.1:8000/api/v1/books/search?title=moon&limit=5" | jq

# Top-rated
curl -s "http://127.0.0.1:8000/api/v1/books/top-rated?limit=5" | jq

# Faixa de preço
curl -s "http://127.0.0.1:8000/api/v1/books/price-range?min=20&max=30&limit=5" | jq

--------------------------------------------------

> Notas
O campo id é 1-based e deriva da ordem do CSV.
O CSV é lido de DATA_CSV (padrão ./data/raw/books.csv).

--------------------------------------------------

## Diagrama
Veja os diagramas em (./docs/diagrams.md).
