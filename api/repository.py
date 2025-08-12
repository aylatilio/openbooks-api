# Data-access layer backed by a CSV file. Keeps API decoupled from the storage.

from pathlib import Path
from typing import List, Optional
import pandas as pd
import datetime as dt

# Expected CSV schema
EXPECTED = ["title", "price", "rating", "availability", "category", "image_url", "product_url"]


def _load_df(csv_path: Path) -> pd.DataFrame:
    """Load CSV with stable schema; return empty frame if missing."""
    if not csv_path.exists():
        return pd.DataFrame(columns=EXPECTED)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    for col in EXPECTED:
        if col not in df.columns:
            df[col] = None
    return df[EXPECTED].copy()


def _with_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Attach 1-based 'id' column derived from row order."""
    df = df.reset_index(drop=True)
    df["id"] = df.index + 1
    return df


class CSVBookRepository:
    """Thin repository over a CSV; easy to swap for a DB implementation later."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._cache_df: Optional[pd.DataFrame] = None
        self._cache_mtime: Optional[float] = None

    def _df(self) -> pd.DataFrame:
        """Return cached DataFrame; reload if file mtime changed."""
        mtime = self.csv_path.stat().st_mtime if self.csv_path.exists() else None
        if self._cache_df is None or mtime != self._cache_mtime:
            self._cache_df = _with_ids(_load_df(self.csv_path))
            self._cache_mtime = mtime
        return self._cache_df

    # ---------- Core queries ----------

    def health(self) -> dict:
        """Basic dataset status and metadata."""
        exists = self.csv_path.exists()
        rows = int(len(self._df())) if exists else 0
        last_updated = (
            dt.datetime.fromtimestamp(self._cache_mtime).isoformat()
            if self._cache_mtime else None
        )
        return {"status": "ok", "csv_exists": exists, "rows": rows, "last_updated": last_updated}

    def list(self, limit: int, offset: int) -> List[dict]:
        """Paginated listing."""
        df = self._df().iloc[offset: offset + limit]
        return [row.to_dict() for _, row in df.iterrows()]

    def get(self, book_id: int) -> Optional[dict]:
        """Get a single row by 1-based id."""
        df = self._df()
        if 1 <= book_id <= len(df):
            return df.iloc[book_id - 1].to_dict()
        return None

    def search(self, title: Optional[str], category: Optional[str], limit: int, offset: int) -> List[dict]:
        """Filter by optional title/category (case-insensitive), with pagination."""
        df = self._df()
        if title:
            df = df[df["title"].str.contains(title, case=False, na=False)]
        if category:
            df = df[df["category"].str.contains(category, case=False, na=False)]
        df = df.iloc[offset: offset + limit]
        return [row.to_dict() for _, row in df.iterrows()]

    def categories(self) -> List[str]:
        """Unique categories sorted alphabetically (empties trimmed)."""
        df = self._df()
        return sorted(c for c in df["category"].dropna().unique().tolist() if str(c).strip())

    # ---------- Stats / insights ----------

    def _numeric_price(self, df: pd.DataFrame) -> pd.DataFrame:
        """Coerce 'price' to numeric for stats/filters."""
        df = df.copy()
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        return df

    def stats_overview(self) -> dict:
        """Return total_books, avg_price, and ratings_distribution."""
        df = self._numeric_price(self._df())
        total = int(len(df))
        if total == 0:
            return {
                "total_books": 0,
                "avg_price": 0.0,
                "ratings_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            }
        avg_price = float(df["price"].mean(skipna=True)) if "price" in df else 0.0
        vc = df["rating"].value_counts(dropna=True).to_dict()
        dist = {str(int(k)): int(v) for k, v in vc.items()}
        for k in ("1", "2", "3", "4", "5"):
            dist.setdefault(k, 0)
        return {"total_books": total, "avg_price": round(avg_price, 2), "ratings_distribution": dist}

    def stats_by_category(self) -> List[dict]:
        """Per-category metrics sorted by count desc."""
        df = self._numeric_price(self._df())
        if df.empty:
            return []
        g = (
            df.groupby("category", dropna=True)["price"]
              .agg(count="count", avg="mean", min="min", max="max")
              .reset_index()
              .sort_values(["count", "category"], ascending=[False, True])
        )
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

    def top_rated(self, limit: int) -> List[dict]:
        """Top-N by rating desc; tie-break by id asc."""
        df = self._df().copy()
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df = df.sort_values(["rating", "id"], ascending=[False, True], na_position="last").head(limit)
        return [row.to_dict() for _, row in df.iterrows()]

    def price_range(self, min_price: float, max_price: float, limit: int, offset: int) -> List[dict]:
        """Filter by inclusive [min_price, max_price], sort by price asc then id."""
        df = self._numeric_price(self._df())
        df = df[df["price"].between(min_price, max_price, inclusive="both")]
        df = df.sort_values(["price", "id"], ascending=[True, True]).iloc[offset: offset + limit]
        return [row.to_dict() for _, row in df.iterrows()]

    def features(self, limit: int, offset: int) -> List[dict]:
        """Normalized columns for ML consumption."""
        df = self._numeric_price(self._df())
        if df.empty:
            return []
        out = df.loc[:, ["id", "title", "price", "rating", "category"]].copy()
        out["category"] = out["category"].astype(str).str.strip()
        out = out.iloc[offset: offset + limit]
        return [row.to_dict() for _, row in out.iterrows()]

    def training_data(self, limit: int, offset: int) -> List[dict]:
        """Alias to features (kept separate for future evolution)."""
        return self.features(limit=limit, offset=offset)

    def avg_price(self) -> float:
        """Dataset mean price (0.0 if empty)."""
        df = self._numeric_price(self._df())
        return 0.0 if df.empty else float(df["price"].mean(skipna=True))
