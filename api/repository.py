# Repository: CSV-backed data-access layer for books
# Responsibilities: load/cache dataset and provide query/insight methods

# Data-access layer for the books dataset backed by a CSV file

from pathlib import Path
from typing import List, Optional
import pandas as pd
import datetime as dt

# Expected CSV schema
EXPECTED = ["title", "price", "rating", "availability", "category", "image_url", "product_url"]


def _load_df(csv_path: Path) -> pd.DataFrame:
    """
    Load the CSV with a stable schema. Returns an empty DataFrame if the file is missing.
    Uses 'utf-8-sig' to handle BOM on Windows.
    """
    if not csv_path.exists():
        return pd.DataFrame(columns=EXPECTED)

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    # Be defensive about unexpected columns or ordering
    for col in EXPECTED:
        if col not in df.columns:
            df[col] = None
    return df[EXPECTED].copy()


def _with_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attach a 1-based 'id' column derived from row order, used as a stable public identifier.
    """
    df = df.reset_index(drop=True)
    df["id"] = df.index + 1
    return df


class CSVBookRepository:
    """
    Thin repository around a CSV file.
    - Encapsulates loading/caching logic.
    - Provides query methods used by the API layer.
    - Easy to replace with a DB-backed repository in the future.
    """

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._cache_df: Optional[pd.DataFrame] = None
        self._cache_mtime: Optional[float] = None

    def _df(self) -> pd.DataFrame:
        """
        Return a cached DataFrame. Reloads if the CSV changed on disk.
        """
        mtime = self.csv_path.stat().st_mtime if self.csv_path.exists() else None
        if self._cache_df is None or mtime != self._cache_mtime:
            self._cache_df = _with_ids(_load_df(self.csv_path))
            self._cache_mtime = mtime
        return self._cache_df

    # ---------- Core queries ----------

    def health(self) -> dict:
        """
        Basic dataset status for health checks.
        """
        exists = self.csv_path.exists()
        rows = int(len(self._df())) if exists else 0
        last_updated = (
            dt.datetime.fromtimestamp(self._cache_mtime).isoformat()
            if self._cache_mtime else None
        )
        return {"status": "ok", "csv_exists": exists, "rows": rows, "last_updated": last_updated}

    def list(self, limit: int, offset: int) -> List[dict]:
        """
        Paginated listing.
        """
        df = self._df().iloc[offset : offset + limit]
        return [row.to_dict() for _, row in df.iterrows()]

    def get(self, book_id: int) -> Optional[dict]:
        """
        Get a single row by 1-based id.
        """
        df = self._df()
        if 1 <= book_id <= len(df):
            return df.iloc[book_id - 1].to_dict()
        return None

    def search(
        self,
        title: Optional[str],
        category: Optional[str],
        limit: int,
        offset: int
    ) -> List[dict]:
        """
        Filter by optional title/category (case-insensitive), with pagination.
        """
        df = self._df()
        if title:
            df = df[df["title"].str.contains(title, case=False, na=False)]
        if category:
            df = df[df["category"].str.contains(category, case=False, na=False)]
        df = df.iloc[offset : offset + limit]
        return [row.to_dict() for _, row in df.iterrows()]

    def categories(self) -> List[str]:
        """
        Unique categories sorted alphabetically (empties trimmed).
        """
        df = self._df()
        return sorted(c for c in df["category"].dropna().unique().tolist() if str(c).strip())

    # ---------- Stats / insights ----------

    def _numeric_price(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure 'price' is numeric for stats (coerce just in case).
        """
        df = df.copy()
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        return df

    def stats_overview(self) -> dict:
        """
        High-level dataset metrics.
        """
        df = self._df()
        df = self._numeric_price(df)

        total_books = int(len(df))
        categories_count = int(df["category"].nunique(dropna=True))
        avg_price = float(df["price"].mean(skipna=True)) if total_books else 0.0

        # rating distribution as { "1": 123, "2": 456, ... }
        rating_counts = (
            df["rating"].value_counts(dropna=True).sort_index().to_dict()
            if total_books else {}
        )
        rating_counts = {str(int(k)): int(v) for k, v in rating_counts.items()}

        min_price = float(df["price"].min(skipna=True)) if total_books else 0.0
        max_price = float(df["price"].max(skipna=True)) if total_books else 0.0

        return {
            "total_books": total_books,
            "categories_count": categories_count,
            "avg_price": round(avg_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "rating_distribution": rating_counts,
        }

    def stats_by_category(self) -> List[dict]:
        """
        Category-level metrics sorted by book count (desc).
        """
        df = self._df()
        df = self._numeric_price(df)
        if df.empty:
            return []

        g = (
            df.groupby("category", dropna=True)["price"]
              .agg(count="count", avg="mean", min="min", max="max")
              .reset_index()
        )
        g = g.sort_values(["count", "category"], ascending=[False, True])

        out: List[dict] = []
        for _, row in g.iterrows():
            out.append({
                "category": str(row["category"]),
                "count": int(row["count"]),
                "avg_price": round(float(row["avg"]), 2),
                "min_price": round(float(row["min"]), 2),
                "max_price": round(float(row["max"]), 2),
            })
        return out
