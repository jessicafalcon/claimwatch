"""The Opinion Assurances microdata parser (spec Phase 3a, amendment A1;
invariant 6): review scopes to review rows, the aggregate to one snapshot row,
the author scope never read, the page the unit of refusal. Every negative case
is built in memory by mutating the frozen sample."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from ingest.opinion_assurances import REVIEW_SCALE, SAMPLE_DIR, parse
from ingest.parsed import REVIEW_RATINGS, PageShapeError, review_rating
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
        assert row["rating"] in REVIEW_RATINGS
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
            lambda s: s.replace('<meta itemprop="ratingValue" content="4.5">', "", 1),
            "is missing",
        ),
        (
            "ratingValue",
            lambda s: s.replace(
                '<meta itemprop="ratingValue" content="4.5">',
                '<meta itemprop="ratingValue" content="6">',
                1,
            ),
            "not a half-step 1..5",
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
        lambda s: s.replace('<meta itemprop="ratingValue" content="4.5">', "", 1),
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


@pytest.mark.parametrize("value", ["many", "-1", "2147483648", "100000000000"])
def test_aggregate_count_outside_the_shape_is_refused(value):
    """Including a count past the column's ceiling (round 2)."""
    html = _page(1).replace(
        '<meta itemprop="ratingCount" content="512">',
        f'<meta itemprop="ratingCount" content="{value}">',
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


def test_a_pathological_page_parses_in_linear_time():
    """Round 1, security-reviewer #1: thousands of unclosed elements followed by
    thousands of stray closers must not make the walker rescan its stack —
    the parse stays well under a second and the sample's rows come out
    unchanged."""
    import time

    junk = "<div>" * 20000 + "</span>" * 20000
    html = _page(1).replace("<body>", "<body>" + junk)
    t0 = time.perf_counter()
    parsed = parse(html, PAGE_URL, CAPTURED, SRC)
    assert time.perf_counter() - t0 < 1.0
    assert len(parsed.reviews) == pins.OA_SAMPLE_REVIEWS_ON_PAGES[0]


def test_two_rating_values_in_one_review_refuse_the_page():
    """Round 1, functionality-tester F2: a second ratingValue used to win
    silently; the shape declares one, so two refuse the page."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            '<meta itemprop="ratingValue" content="4.5">',
            '<meta itemprop="ratingValue" content="4.5">'
            '<meta itemprop="ratingValue" content="1">',
            1,
        ),
    )
    with pytest.raises(
        PageShapeError, match="review 2': field 'ratingValue' appears 2 times"
    ):
        parse(html, PAGE_URL, CAPTURED, SRC)
    twice = _page(1).replace(
        '<meta itemprop="ratingCount" content="512">',
        '<meta itemprop="ratingCount" content="512">'
        '<meta itemprop="ratingCount" content="9">',
    )
    with pytest.raises(PageShapeError, match="'ratingCount' appears twice"):
        parse(twice, PAGE_URL, CAPTURED, SRC)


def test_a_nested_review_scope_refuses_the_page():
    """A review scope inside another used to be dropped without a word; it is
    outside the declared shape and refuses the page."""
    scopes = _page(1).split('itemtype="https://schema.org/review"')
    inner = (
        '<div itemscope itemtype="https://schema.org/review" itemprop="review">'
        '<div itemscope itemprop="reviewRating" itemtype="https://schema.org/Rating">'
        '<meta itemprop="ratingValue" content="4"></div>'
        '<div class="oa_description">Avis publié le 01/08/2026 '
        "suite à une expérience le 01/07/2026"
        '<h4 class="oa_text">EXEMPLE FICTIF. Imbriqué.</h4></div></div>'
    )
    scopes[1] = scopes[1].replace(
        '<div class="oa_description">', inner + '<div class="oa_description">', 1
    )
    html = 'itemtype="https://schema.org/review"'.join(scopes)
    with pytest.raises(
        PageShapeError, match="field 'review' 1 review scope\(s\) nested"
    ):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_the_sample_carries_the_live_nesting_text_after_the_description():
    """A5: the first live page refused because `h4.oa_text` FOLLOWS
    `div.oa_description` while the first sample nested it inside. The sample
    now carries the live nesting: the description's element holds its
    sentence and nothing else."""
    for n in (1, 2):
        for m in re.finditer(
            r'<div class="oa_description">(.*?)</div>', _page(n), flags=re.S
        ):
            assert "oa_text" not in m.group(1)
            assert m.group(1).strip().startswith("Avis publié le")


def test_a_body_nested_inside_the_description_is_still_the_review_text():
    """A5: the guard's kind is "this element is the review's text", not "this
    element is inside the description" — the first sample's nesting still
    reads to the same rows."""
    nested = re.sub(
        r'(<div class="oa_description">\n\s+Avis publié le [^\n]+\n)(\s+</div>\n)'
        r'(\s+<h4 class="oa_text[^\n]*\n[^\n]*\n\s+</h4>\n)',
        lambda m: m.group(1) + m.group(3) + m.group(2),
        _page(1),
    )
    assert nested != _page(1) and nested.count("oa_text") == _page(1).count("oa_text")
    assert parse(nested, PAGE_URL, CAPTURED, SRC) == parse(
        _page(1), PAGE_URL, CAPTURED, SRC
    )


def test_two_bodies_in_one_review_refuse_the_page():
    """A5: the shape declares one `oa_text` per review; two refuse the page
    naming the count, as two `ratingValue`s do."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            '<div class="oa_commands',
            '<h4 class="oa_text">EXEMPLE FICTIF. Second texte.</h4>'
            '<div class="oa_commands',
            1,
        ),
    )
    with pytest.raises(
        PageShapeError, match="review 2': field 'oa_text' appears 2 times"
    ):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_two_bodies_one_nested_in_the_other_refuse_the_page():
    """A5's "exactly one `oa_text`" counts elements, not openings: a body
    nested inside the body is a second one and refuses like a sibling, never
    two texts merged into one row (round 4, code-reviewer #7,
    functionality-tester #2)."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            '<h4 class="oa_text my-xl-4 my-3">',
            '<h4 class="oa_text my-xl-4 my-3"><span class="oa_text">INNER.</span>',
            1,
        ),
    )
    assert html != _page(1)
    with pytest.raises(
        PageShapeError, match="review 2': field 'oa_text' appears 2 times"
    ):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_a_body_inside_the_author_markup_is_neither_read_nor_counted():
    """Author markup is never read: an `oa_text` inside it is layout, not a
    second body."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            "profil</a>",
            'profil</a><h4 class="oa_text">reviewer-placeholder-9 wrote this</h4>',
            1,
        ),
    )
    rows = parse(html, PAGE_URL, CAPTURED, SRC).reviews
    assert rows[1] == parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews[1]


@pytest.mark.parametrize("value", ["1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"])
def test_every_half_step_is_a_review_rating(value):
    """A6: the site rates in half stars; each member of the closed set maps
    to the column's value, exactly."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            '<meta itemprop="ratingValue" content="4.5">',
            f'<meta itemprop="ratingValue" content="{value}">',
            1,
        ),
    )
    assert html != _page(1) or value == "4.5"
    rows = parse(html, PAGE_URL, CAPTURED, SRC).reviews
    assert rows[1]["rating"] == Decimal(value)
    assert rows[1]["rating"] in REVIEW_RATINGS


@pytest.mark.parametrize("value", ["4.0", "4.25", "0.5", "6", "5.5", "", "4,5", " 4"])
def test_a_rating_outside_the_half_steps_refuses_the_page(value):
    """A6: the set is closed and the parse strict — a spelling the site does
    not use, or a value off the scale, refuses naming the value."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            '<meta itemprop="ratingValue" content="4.5">',
            f'<meta itemprop="ratingValue" content="{value}">',
            1,
        ),
    )
    with pytest.raises(
        PageShapeError, match="review 2': field 'ratingValue' is not a half-step 1..5"
    ):
        parse(html, PAGE_URL, CAPTURED, SRC)


def test_review_rating_is_a_lookup_in_the_one_declared_set():
    """A6, declared once: `review_rating` accepts a value iff its spelling is
    a member's — no second copy of the nine values as a pattern, no text
    reaching `Decimal()`. A member however its source spells a number (a
    digit string, an int, a Decimal with a trailing zero) is the member; a
    string with a trailing zero, a float, a bool, an exponent or a leading
    zero is not (round 4, code-reviewer #6; functionality-tester #5)."""
    assert {review_rating(str(r)) for r in REVIEW_RATINGS} == set(REVIEW_RATINGS)
    assert review_rating(4) == Decimal(4) and review_rating("4") == Decimal(4)
    assert review_rating(Decimal("4.0")) == Decimal(4)
    assert review_rating(Decimal("4.50")) == Decimal("4.5")
    for outside in ("1.0", "1.50", 4.5, True, False, "1e0", "01", "1.", None, [4]):
        assert review_rating(outside) is None, outside
    for bad_decimal in (Decimal("NaN"), Decimal("Infinity"), Decimal("4.25")):
        assert review_rating(bad_decimal) is None, bad_decimal


def test_the_sample_carries_one_half_step():
    """The frozen sample's second review rates 4.5 (pins.OA_SAMPLE_HALF_STEP),
    so the samples rebuild exercises the half-step end to end."""
    rows = parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews
    day, rating = pins.OA_SAMPLE_HALF_STEP
    assert (rows[1]["review_date"], rows[1]["rating"]) == (day, Decimal(rating))
    assert [r["rating"] for r in rows].count(Decimal(rating)) == 1


def test_the_set_admits_exactly_the_scale_the_site_declares():
    """A6: the site declares each review's scale in its own markup; our closed
    set's bounds are read back from the sample's declaration, so we admit a
    value iff the site admits it."""
    worst = set(re.findall(r'itemprop="worstRating" content="([^"]*)"', _page(1)))
    best = set(re.findall(r'itemprop="bestRating" content="([^"]*)"', _page(1)))
    assert worst == {"1", "0"} and best == {"5"}  # reviews 1..5; the aggregate 0..5
    assert (min(REVIEW_RATINGS), max(REVIEW_RATINGS)) == (Decimal(1), Decimal(5))
    assert REVIEW_SCALE == ("1", "5")


@pytest.mark.parametrize(
    ("mutate", "declared"),
    [
        (
            lambda s: s.replace(
                'worstRating" content="1"', 'worstRating" content="0"', 1
            ),
            "'0'..'5'",
        ),
        (
            lambda s: s.replace(
                'bestRating" content="5"', 'bestRating" content="10"', 1
            ),
            "'1'..'10'",
        ),
        (
            lambda s: s.replace('<meta itemprop="worstRating" content="1">', "", 1),
            "None..'5'",
        ),
    ],
)
def test_a_review_declaring_another_scale_refuses_the_page(mutate, declared):
    """A6: a page whose review scale is not 1..5 — a site that starts admitting
    0.5, say — refuses naming the declared bounds; the set is widened by hand,
    with the page as evidence, never by the parse."""
    html = _second_review(_page(1), mutate)
    assert html != _page(1)
    with pytest.raises(
        PageShapeError,
        match=(
            "review 2': field 'worstRating/bestRating' declares the scale "
            f"{re.escape(declared)}, not 1..5"
        ),
    ):
        parse(html, PAGE_URL, CAPTURED, SRC)


AGGREGATE_OPEN = (
    '<div class="oa_scoring d-flex flex-column" itemprop="aggregateRating" '
    'itemscope itemtype="http://schema.org/AggregateRating">'
)
INNER_AGGREGATE = (
    '<div itemscope itemtype="http://schema.org/AggregateRating" '
    'itemprop="aggregateRating">'
    '<meta itemprop="ratingCount" content="99999">'
    '<meta itemprop="ratingValue" content="1"></div>'
)


def test_an_aggregate_nested_in_a_review_refuses_the_page():
    """A page whose only aggregate sits inside one review's markup used to
    yield that review's numbers as the profile-wide snapshot; it is outside
    the declared shape and refuses (round 2, functionality-tester F1)."""
    html = _page(1)
    assert html.count(AGGREGATE_OPEN) == 1
    head, tail = html.split(AGGREGATE_OPEN, 1)
    block_end = tail.index("</div>") + len("</div>")
    without = head + tail[block_end:]  # the page-level aggregate removed
    with pytest.raises(PageShapeError, match="'aggregateRating' is missing"):
        parse(without, PAGE_URL, CAPTURED, SRC)
    nested = without.replace(
        '<div class="oa_description">',
        INNER_AGGREGATE + '<div class="oa_description">',
        1,
    )
    with pytest.raises(
        PageShapeError, match=r"'aggregateRating' 1 aggregate scope\(s\) nested"
    ):
        parse(nested, PAGE_URL, CAPTURED, SRC)


def test_an_aggregate_nested_in_the_aggregate_refuses_the_page():
    """An aggregate inside the aggregate used to merge its values into the
    outer one without a word; it refuses too (round 2, code-reviewer #8)."""
    html = _page(1).replace(AGGREGATE_OPEN, AGGREGATE_OPEN + INNER_AGGREGATE, 1)
    with pytest.raises(PageShapeError, match=r"1 aggregate scope\(s\) nested"):
        parse(html, PAGE_URL, CAPTURED, SRC)


@pytest.mark.parametrize(
    "markup",
    [
        '<span itemprop="author">reviewer-placeholder-9</span>',
        '<div itemscope itemtype="http://schema.org/Person"><span>reviewer-placeholder-9</span></div>',
        '<b itemprop="author"><i>reviewer-placeholder-9</i></b>',
    ],
)
def test_author_markup_without_itemscope_is_still_never_read(markup):
    """Round 1, functionality-tester F3: author markup inside the body element,
    with no itemscope, must not land in `body`; the guard is about persons, not
    about one scope."""
    html = _second_review(
        _page(1),
        lambda s: s.replace(
            '<h4 class="oa_text my-xl-4 my-3">',
            '<h4 class="oa_text my-xl-4 my-3">' + markup,
            1,
        ),
    )
    rows = parse(html, PAGE_URL, CAPTURED, SRC).reviews
    assert (
        rows[1]["body"] == parse(_page(1), PAGE_URL, CAPTURED, SRC).reviews[1]["body"]
    )
    assert "reviewer-placeholder-9" not in rows[1]["body"]


def test_an_absurdly_long_count_refuses_not_tracebacks():
    html = _page(1).replace('content="512"', 'content="' + "9" * 5000 + '"')
    with pytest.raises(PageShapeError, match="'ratingCount'"):
        parse(html, PAGE_URL, CAPTURED, SRC)
