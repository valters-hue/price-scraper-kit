"""Config-driven product/price scraper.

Usage:
    python scraper.py sites.example.json --out output/products.csv
    python scraper.py sites.example.json --out output/products.xlsx --max-pages 5

Each site in the config lists CSS selectors for the item card and its fields,
plus an optional "next page" selector. Output: CSV, Excel or JSON (by file
extension), one row per item, with a parsed numeric price and currency.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from prices import parse_price

log = logging.getLogger("scraper")
USER_AGENT = "PriceScraperKit/1.0 (+https://github.com/valters-hue/price-scraper-kit)"


@dataclass
class SiteConfig:
    name: str
    start_url: str
    item: str
    fields: dict[str, str | dict]
    next_page: str | None = None
    price_field: str = "price"
    delay_seconds: float = 1.0
    max_pages: int = 50
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "SiteConfig":
        return cls(**d)


class Fetcher:
    """requests.Session with retries, backoff, polite delays and robots.txt."""

    def __init__(self, retries: int = 3, timeout: float = 20.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.retries = retries
        self.timeout = timeout
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        base = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                resp = self.session.get(base + "/robots.txt", timeout=self.timeout)
                rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        return self._robots[base].can_fetch(USER_AGENT, url)

    def get(self, url: str, headers: dict[str, str] | None = None) -> str:
        last_err: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, headers=headers or {}, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or resp.encoding
                return resp.text
            except requests.RequestException as err:
                last_err = err
                wait = 2 ** attempt + random.random()
                log.warning("%s failed (%s), retry %d/%d in %.1fs", url, err, attempt, self.retries, wait)
                time.sleep(wait)
        raise RuntimeError(f"Giving up on {url}: {last_err}")


def extract(html: str, site: SiteConfig, page_url: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select(site.item):
        row: dict[str, str | float | None] = {"site": site.name}
        for name, spec in site.fields.items():
            # A field is "css selector", "css selector@attribute", or
            # {"selector": "...", "regex": "..."} to keep only a regex group.
            selector, pattern = (spec["selector"], spec.get("regex")) if isinstance(spec, dict) else (spec, None)
            attr = None
            if "@" in selector:  # "a@href" → attribute of the element
                selector, attr = selector.rsplit("@", 1)
            el = card.select_one(selector) if selector else card
            if el is None:
                value = None
            elif attr:
                value = el.get(attr)
                if isinstance(value, list):  # e.g. class="star-rating Three"
                    value = " ".join(value)
                if attr in ("href", "src") and value:
                    value = urljoin(page_url, value)
            else:
                value = " ".join(el.get_text(" ", strip=True).split())
            if pattern and value is not None:
                m = re.search(pattern, value)
                value = (m.group(1) if m.groups() else m.group(0)) if m else None
            row[name] = value
        price = parse_price(str(row.get(site.price_field) or ""))
        row["price_value"] = price.amount if price else None
        row["currency"] = price.currency if price else None
        row["page_url"] = page_url
        rows.append(row)
    next_url = None
    if site.next_page:
        nxt = soup.select_one(site.next_page)
        if nxt is not None and nxt.get("href"):
            next_url = urljoin(page_url, nxt["href"])
    return rows, next_url


def crawl(site: SiteConfig, fetcher: Fetcher, max_pages: int | None = None) -> Iterator[dict]:
    url: str | None = site.start_url
    seen: set[str] = set()
    limit = max_pages or site.max_pages
    pages = 0
    while url and url not in seen and pages < limit:
        if not fetcher.allowed(url):
            log.warning("robots.txt disallows %s, stopping this site", url)
            return
        seen.add(url)
        html = fetcher.get(url, site.headers)
        rows, url = extract(html, site, url)
        pages += 1
        log.info("%s page %d: %d items", site.name, pages, len(rows))
        yield from rows
        if url:
            time.sleep(site.delay_seconds)


def write_output(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for r in rows:
        r["scraped_at"] = scraped_at
    cols: list[str] = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    suffix = out.suffix.lower()
    if suffix == ".json":
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif suffix in (".xlsx", ".xls"):
        import pandas as pd  # optional dependency, only for Excel

        pd.DataFrame(rows, columns=cols).to_excel(out, index=False)
    else:
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scrape product listings defined in a JSON config.")
    ap.add_argument("config", type=Path)
    ap.add_argument("--out", type=Path, default=Path("output/products.csv"))
    ap.add_argument("--max-pages", type=int, default=None, help="override max pages per site")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    sites = [SiteConfig.from_dict(s) for s in json.loads(args.config.read_text(encoding="utf-8"))["sites"]]
    fetcher = Fetcher()
    rows: list[dict] = []
    for site in sites:
        try:
            rows.extend(crawl(site, fetcher, args.max_pages))
        except RuntimeError as err:
            log.error("%s: %s", site.name, err)
    if not rows:
        print("No rows scraped. Check the selectors in your config.", file=sys.stderr)
        return 1
    write_output(rows, args.out)
    priced = sum(1 for r in rows if r.get("price_value") is not None)
    print(f"Saved {len(rows)} rows ({priced} with a parsed price) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
