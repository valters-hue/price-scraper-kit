import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper import SiteConfig, extract  # noqa: E402

HTML = """
<ol>
  <li><article class="product_pod">
    <h3><a href="item-1/index.html" title="Book One">Book One</a></h3>
    <p class="star-rating Three"></p>
    <p class="price_color">£51.77</p>
  </article></li>
  <li><article class="product_pod">
    <h3><a href="item-2/index.html" title="Book Two">Book Two</a></h3>
    <p class="star-rating One"></p>
    <p class="price_color">1.234,50 €</p>
  </article></li>
</ol>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
"""

SITE = SiteConfig(
    name="demo",
    start_url="https://example.com/catalogue/page-1.html",
    item="article.product_pod",
    fields={
        "title": "h3 a@title",
        "price": "p.price_color",
        "rating": {"selector": "p.star-rating@class", "regex": r"star-rating (\w+)"},
        "url": "h3 a@href",
    },
    next_page="li.next a",
)


def test_extract_rows_and_next_page():
    rows, nxt = extract(HTML, SITE, SITE.start_url)
    assert [r["title"] for r in rows] == ["Book One", "Book Two"]
    assert [r["rating"] for r in rows] == ["Three", "One"]
    assert rows[0]["url"] == "https://example.com/catalogue/item-1/index.html"
    assert (rows[0]["price_value"], rows[0]["currency"]) == (51.77, "GBP")
    assert (rows[1]["price_value"], rows[1]["currency"]) == (1234.5, "EUR")
    assert nxt == "https://example.com/catalogue/page-2.html"


def test_missing_field_is_none():
    rows, _ = extract('<article class="product_pod"><h3><a title="X">X</a></h3></article>', SITE, SITE.start_url)
    assert rows[0]["price"] is None and rows[0]["price_value"] is None
