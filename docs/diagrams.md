# OpenBooks API — Diagrams

This document collects the architecture and flow diagrams for the OpenBooks API.  

```mermaid
graph TD
    U[Client<br/>(Browser/REST Client)] -->|HTTP| A[FastAPI (Uvicorn)]
    A -->|read| R[CSVBookRepository]
    R -->|read-only| F[(data/raw/books.csv)]
    A -->|Swagger UI| D[/docs]

    ```

```mermaid
sequenceDiagram
    actor User
    participant Client
    participant API as FastAPI
    participant Repo as CSVBookRepository
    participant CSV as books.csv

    User->>Client: Trigger request (e.g., tests.http)
    Client->>API: GET /api/v1/books?limit=&offset=
    API->>Repo: list(limit, offset)
    Repo->>CSV: Load/cache DataFrame
    CSV-->>Repo: Selected rows
    Repo-->>API: List of dicts
    API-->>Client: 200 OK (JSON)

    ```

```mermaid
graph LR
    Dev[GitHub Repo] -- push --> Render[Render Web Service]
    Render --> U[Uvicorn + FastAPI]
    U --> F[(data/raw/books.csv in the repo)]
    U --> D[/docs]

    ```
