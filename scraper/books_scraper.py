# Libraries
import csv, re, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup

# Base URLs for scraping target
BASE = "https://books.toscrape.com/"
CATALOGUE = "https://books.toscrape.com/catalogue/"

# Output CSV file path
OUT_CSV = Path(__file__).resolve().parents[1] / "data" / "raw" / "books.csv"

# HTTP headers to simulate a real browser request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
}

# Mapping from star rating text to numeric value
RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

# Data structure to store book information
@dataclass
class Book:
    title: str
    price: float
    rating: int
    availability: str
    category: str
    image_url: str
    product_url: str

# Fetches and parses HTML
def get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"  # ensure correct decoding
    return BeautifulSoup(r.text, "html.parser")

# Extracts all book categories from the homepage
def extract_categories() -> List[Tuple[str, str]]:
    soup = get_soup(BASE)
    cats: List[Tuple[str, str]] = []
    for a in soup.select("div.side_categories ul li ul li a"):
        name = a.get_text(strip=True)
        href = a.get("href")
        if href and name:
            cats.append((name, requests.compat.urljoin(BASE, href)))
    return cats

# Converts star rating text from CSS class into a numeric value
def parse_rating(tag) -> int:
    classes = tag.get("class", []) if tag else []
    for c in classes:
        if c in RATING_MAP:
            return RATING_MAP[c]
    return 0

# Cleans price text and parses into a float
def parse_price(text: str) -> float:
    return float(re.sub(r"[^0-9.]", "", text))

# Scrapes all books from a given category (with pagination)
def scrape_category(name: str, url: str) -> Iterable[Book]:
    next_url = url
    while next_url:
        soup = get_soup(next_url)
        for art in soup.select("article.product_pod"):
            title = art.h3.a.get("title", "").strip()
            price = parse_price(art.select_one("p.price_color").get_text(strip=True))
            rating = parse_rating(art.select_one("p.star-rating"))

            # Construct absolute product URL
            product_rel = art.h3.a.get("href", "")
            product_url = requests.compat.urljoin(CATALOGUE, product_rel.replace("../../../", ""))

            # Fetch product detail page
            detail = get_soup(product_url)
            availability = detail.select_one("p.instock.availability")
            availability_text = availability.get_text(strip=True) if availability else ""
            img = detail.select_one("div.item.active img")
            img_src = img.get("src") if img else ""
            image_url = requests.compat.urljoin(BASE, img_src.replace("../", ""))

            yield Book(
                title=title,
                price=price,
                rating=rating,
                availability=availability_text,
                category=name,
                image_url=image_url,
                product_url=product_url,
            )

            # Adds a short delay to avoid overwhelming the server and reduce blocking risk
            time.sleep(0.03)

        # Find next page if available
        next_li = soup.select_one("li.next > a")
        next_url = requests.compat.urljoin(next_url, next_li.get("href")) if next_li else None

# Main scraper function
def run():
    print("[scraper] Fetching categories…")
    cats = extract_categories()
    print(f"[scraper] {len(cats)} categories found.")

    rows = []
    for idx, (name, url) in enumerate(cats, start=1):
        print(f"[scraper] ({idx}/{len(cats)}) Category: {name}")
        for book in scrape_category(name, url):
            rows.append(asdict(book))

    # Write results to CSV (UTF-8 with BOM)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["title","price","rating","availability","category","image_url","product_url"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[scraper] Completed! {len(rows)} books saved to {OUT_CSV}")

# Entry point
if __name__ == "__main__":
    run()
