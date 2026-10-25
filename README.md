# Price Scraper Kit

A small, config-driven Python scraper for product listings and prices. Point it at a site with a few CSS selectors and get a clean CSV, Excel or JSON file, with every price parsed into a number and a currency.

```
$ python scraper.py sites.example.json --out sample_output/books.csv
Saved 1000 rows (1000 with a parsed price) to sample_output/books.csv
```

The example config scrapes all 50 pages of [books.toscrape.com](https://books.toscrape.com), a sandbox site built for scraping practice, in under a minute. See [`sample_output/books.csv`](sample_output/books.csv).

| title | price | rating | price_value | currency |
|---|---|---|---|---|
| A Light in the Attic | £51.77 | Three | 51.77 | GBP |
| Tipping the Velvet | £53.74 | One | 53.74 | GBP |
| Soumission | £50.10 | One | 50.10 | GBP |

## Features

- **One JSON config per site.** Item selector, field selectors (`"h3 a@title"` reads an attribute), optional regex per field, and a "next page" selector for pagination.
- **Prices you can sort and sum.** `£51.77`, `$1,234.56`, `1.234,56 €`, `1 234,56 EUR`, `CHF 1'250.00` and `99 zł` all become a number plus an ISO currency code.
- **Polite and resilient.** Checks `robots.txt`, waits between pages, retries 429/5xx with exponential backoff, and stops on repeated URLs.
- **Output by file extension.** `.csv` (Excel-friendly UTF-8), `.xlsx` or `.json`, with a `scraped_at` timestamp on every row.
- **Tested.** `pytest` covers price parsing across US/EU formats and HTML extraction from a fixture, no network needed.

## Quick start

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python scraper.py sites.example.json --out output/products.xlsx --max-pages 5 -v
pytest -q
```

## Add your own site

```json
{
  "sites": [{
    "name": "my-shop",
    "start_url": "https://example.com/category?page=1",
    "item": ".product-card",
    "fields": {
      "title": ".product-title",
      "price": ".price",
      "sku": {"selector": ".sku", "regex": "SKU:\\s*(\\S+)"},
      "url": "a@href"
    },
    "next_page": "a[rel=next]",
    "delay_seconds": 1.0
  }]
}
```

For JavaScript-heavy sites, the same config works with a Playwright fetcher in place of `requests` (available on request).

## Responsible use

Scrape only public pages you are allowed to access, respect each site's terms and `robots.txt`, and keep request rates low.

## License

MIT
