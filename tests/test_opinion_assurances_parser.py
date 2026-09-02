"""The Opinion Assurances microdata parser (spec Phase 3a, amendment A1;
invariant 6): review scopes to review rows, the aggregate to one snapshot row,
the author scope never read, the page the unit of refusal. Every negative case
is built in memory by mutating the frozen sample."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from ingest.opinion_assurances import SAMPLE_DIR, parse
from ingest.parsed import PageShapeError
from ingest.sources import sample_source
from tests import pins

SRC = sample_source("opinion_assurances")
PAGE_URL = pins.OA_SAMPLE_FIRST_ROW["source_url"]
CAPTURED = pins.OA_SAMPLE_CAPTURED_AT
RAW_COLUMNS = (
    "source",
    "external_id",
    "source_url",
    "captured_at",
    "review_date",
    "rating",
    "title",
    "body",
)


def _page(n: int = 1) -> str:
    return (SAMPLE_DIR / f"page-{n}.html").read_text(encoding="utf-8")


def _second_review(html: str, mutate) -> str:
    """Apply `mutate` to the SECOND review scope's markup: proves the page is the
    unit — one bad review, zero rows."""
    parts = html.split('itemtype="https://schema.org/review"')
    assert len(parts) == 4  # three reviews on page 1
    head = 'itemtype="https://schema.org/review"'
    parts[2] = mutate(parts[2])
    return head.join(parts)


def test_well_formed_page_maps_to_reviews_and_one_snapshot():
    parsed = parse(_page(1), PAGE_URL, CAPTURED, SRC)
    assert len(parsed.reviews) == pins.OA_SAMPLE_REVIEWS_ON_PAGES[0]
    assert len(parsed.snapshots) == 1
    for row in parsed.reviews:
        assert tuple(row) == RAW_COLUMNS
        assert isinstance(row["rating"], int) and 1 <= row["rating"] <= 5
        assert re.fullmatch(r"[0-9a-f]{64}", row["external_id"])  # a content hash
        assert row["body"].startswith("EXEMPLE FICTIF.") and row["title"] == ""
    first = {k: parsed.reviews[0][k] for k in pins.OA_SAMPLE_FIRST_ROW}
    assert first == pins.OA_SAMPLE_FIRST_ROW
    snap = parsed.snapshots[0]
    assert (str(snap["rating"]), snap["review_count"]) == pins.OA_SAMPLE_SNAPSHOT
    assert (snap["origin"], snap["profile"], snap["source"]) == (
        "fetch",
        "sample",
        "opinion-assurances",
    )
    assert snap["one_star_share"] is None  # layout text, never read


def test_review_date_is_the_publication_date_not_the_experience_date():
    rows = parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews
    assert [r["review_date"] for r in rows] == [
        "2026-08-20",
        "2026-08-18",
        "2026-07-11",
    ]


def test_external_id_is_stable_and_author_free():
    """The same review on two pages, or in two captures, hashes to the same id;
    the pseudonym and member link take no part in it."""
    page1 = parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews
    page2 = parse(
        _page(2), PAGE_URL[:-5] + "-page2.html", "2026-09-08T10:00:00", SRC
    ).reviews
    shared = {r["external_id"] for r in page1} & {r["external_id"] for r in page2}
    assert len(shared) == 1  # the paging overlap
    renamed = _page(1).replace("reviewer-placeholder-", "someone-else-")
    assert [
        r["external_id"] for r in parse(renamed, PAGE_URL, CAPTURED, SRC).reviews
    ] == [r["external_id"] for r in page1]
    edited = _page(1).replace("application claire", "application confuse")
    assert (
        parse(edited, PAGE_URL, CAPTURED, SRC).reviews[1]["external_id"]
        != page1[1]["external_id"]
    )


def test_author_scope_is_never_read():
    """Dropping every author scope changes nothing; no row carries a name or a
    member link."""
    html = re.sub(
        r'<div class="oa_title" itemscope itemprop="author".*?</div>',
        "",
        _page(1),
        flags=re.S,
    )
    assert "reviewer-placeholder" not in html
    assert parse(html, PAGE_URL, CAPTURED, SRC) == parse(
        _page(1), PAGE_URL, CAPTURED, SRC
    )
    for row in parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews:
        assert (
            "reviewer-placeholder" not in row["body"] and "membres" not in row["body"]
        )
        assert not {"author", "name"} & set(row)


@pytest.mark.parametrize(
    ("field", "mutate", "why"),
    [
        (
            "ratingValue",
            lambda s: s.replace('<meta itemprop="ratingValue" content="5">', "", 1),
            "is missing",
        ),
        (
            "ratingValue",
            lambda s: s.replace(
                '<meta itemprop="ratingValue" content="5">',
                '<meta itemprop="ratingValue" content="6">',
                1,
            ),
            "not a digit 1..5",
        ),
        (
            "oa_description",
            lambda s: s.replace("Avis publié le", "Avis déposé le", 1),
            "not the declared sentence",
        ),
        (
            "published",
            lambda s: s.replace("publié le 18/08/2026", "publié le 31/02/2026", 1),
            "not a real day",
        ),
        (
            "oa_text",
            lambda s: re.sub(
                r"<h4 class=\"oa_text[^>]*>.*?</h4>",
                '<h4 class="oa_text"></h4>',
                s,
                count=1,
                flags=re.S,
            ),
            "missing or empty",
        ),
    ],
)
def test_missing_required_field_refuses_the_page(field, mutate, why):
    html = _second_review(_page(1), mutate)
    assert html != _page(1)
    with pytest.raises(PageShapeError, match=f"review 2': field '{field}' .*{why}"):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_refusal_names_page_item_and_field():
    html = _second_review(
        _page(1),
        lambda s: s.replace('<meta itemprop="ratingValue" content="5">', "", 1),
    )
    with pytest.raises(PageShapeError) as exc:
        parse(html, PAGE_URL, CAPTURED, SRC)
    message = str(exc.value)
    assert PAGE_URL in message and "review 2" in message and "'ratingValue'" in message
    assert "\n" not in message


def test_a_page_with_the_aggregate_and_no_review_is_the_end_of_the_list():
    parsed = parse(_page(3), PAGE_URL[:-5] + "-page3.html", CAPTURED, SRC)
    assert parsed.is_empty()


def test_a_page_with_neither_aggregate_nor_review_is_refused():
    with pytest.raises(PageShapeError, match="'aggregateRating' is missing"):
        parse("<html><body><p>Erreur</p></body></html>", PAGE_URL, CAPTURED, SRC)
    twice = _page(1).replace(
        "</body>", _page(3).split("<body>")[1].split("<nav")[0] + "</body>"
    )
    with pytest.raises(PageShapeError, match="appears 2 times"):
        parse(twice, PAGE_URL, CAPTURED, SRC)


@pytest.mark.parametrize("value", ["5.5", "abc", "", "3,6"])
def test_aggregate_rating_outside_the_shape_is_refused(value):
    html = _page(1).replace(
        '<meta itemprop="ratingValue" content="3.6">',
        f'<meta itemprop="ratingValue" content="{value}">',
    )
    with pytest.raises(PageShapeError, match="page: field 'ratingValue'"):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_aggregate_count_outside_the_shape_is_refused():
    html = _page(1).replace(
        '<meta itemprop="ratingCount" content="512">',
        '<meta itemprop="ratingCount" content="many">',
    )
    with pytest.raises(PageShapeError, match="'ratingCount'"):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_snapshot_rating_is_kept_to_three_places():
    html = _page(1).replace('content="3.6"', 'content="3.64999"')
    assert parse(html, PAGE_URL, CAPTURED, SRC).snapshots[0]["rating"] == Decimal(
        "3.650"
    )


def test_sample_is_obviously_fake_and_nameless():
    for n in (1, 2, 3):
        html = _page(n)
        assert "hand-written fixture" in html and "FICTIONAL" in html
        assert "exemple-fictif" in PAGE_URL
    for row in parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews:
        assert row["body"].startswith("EXEMPLE FICTIF.")
    assert re.findall(r'itemprop="name">([^<]+)<', _page(1)) == [
        f"reviewer-placeholder-{k}" for k in (1, 2, 3)
    ]
