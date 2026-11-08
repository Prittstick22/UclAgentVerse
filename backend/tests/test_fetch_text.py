from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.clock import SimClock
from app.data.gateway import DataGateway
from scripts.fetch_text import (
    available_at,
    dedupe_news,
    extract_passages,
    fetch_earnings,
    fetch_filings,
    fetch_news,
    map_news,
    month_windows,
)


@pytest.mark.parametrize(
    "published, expected",
    [
        ("2026-07-09T14:00:00Z", "2026-07-09T15:00:00+01:00"),
        ("2026-07-09T15:30:00Z", "2026-07-09T16:30:00+01:00"),
        ("2026-07-09T15:30:01Z", "2026-07-10T16:30:00+01:00"),
        ("2026-07-10T16:00:00Z", "2026-07-13T16:30:00+01:00"),
        ("2026-07-11T09:00:00Z", "2026-07-13T16:30:00+01:00"),
        ("2026-07-12T09:00:00Z", "2026-07-13T16:30:00+01:00"),
        ("2026-10-23T16:00:00Z", "2026-10-26T16:30:00+00:00"),
    ],
)
def test_london_availability(published, expected):
    assert available_at(datetime.fromisoformat(published)) == expected


def test_news_mapping_dedupe_and_gateway_firewall():
    row = {
        "date": "2026-07-10T16:00:00Z",
        "title": "Revenue warning",
        "content": "Supplier risk",
        "link": "https://example.test/article",
    }
    first = map_news(row, "AZN.LSE", "eodhd")
    second = map_news(row, "SHEL.LSE", "eodhd")
    articles = dedupe_news([first, second])
    assert len(articles) == 1
    assert articles[0].tickers == ["AZN.LSE", "SHEL.LSE"]
    assert first.tickers == ["AZN.LSE"]
    snapshot = SimpleNamespace(news=articles, adj_close_gbp=lambda: None)
    clock = SimClock("2026-07-10")
    gateway = DataGateway(clock, snapshot)
    assert gateway.news() == []
    clock.set("2026-07-13")
    assert gateway.news(["SHEL.LSE"]) == articles
    us = map_news(
        {"datetime": 1783670400, "headline": "US news", "summary": "Text", "url": "u"}, "AAPL.US", "finnhub"
    )
    assert us.source == "finnhub" and us.headline == "US news"


def test_month_windows_include_partial_month_and_leap_day():
    assert list(month_windows(date(2024, 2, 28), date(2024, 3, 2))) == [
        ("2024-02-28", "2024-02-29"),
        ("2024-03-01", "2024-03-02"),
    ]


def test_news_routes_and_paginates_without_network():
    us, uk = Mock(), Mock()
    us.company_news.return_value = []
    article = {"date": "2026-07-10T10:00:00Z", "title": "Risk", "link": "https://example.test"}
    uk.news.side_effect = [[article] * 1000, [article]]
    stocks = [{"ticker": "AAPL.US"}, {"ticker": "AZN.LSE"}]
    rows = fetch_news(stocks, us, uk, date(2026, 7, 1), date(2026, 7, 31), pause=lambda _: None)
    us.company_news.assert_called_once_with("AAPL", "2026-07-01", "2026-07-31")
    assert uk.news.call_args_list[1].kwargs["offset"] == 1000
    assert len(rows) == 2
    assert rows[-1].id == "news_syn_inject" and rows[-1].synthetic
    assert rows[-1].source == "synthetic"


def test_passages_strip_markup_limit_size_and_keep_stable_ids():
    html = "<script>risk hidden</script><p>irrelevant</p>" + "".join(
        f"<p>Revenue <b>risk</b> {i} &amp; {'x' * 700}</p>" for i in range(12)
    )
    rows = extract_passages(html, "filing_test")
    assert len(rows) == 10
    assert [row.id for row in rows] == [f"filing_test#p{i}" for i in range(1, 11)]
    assert all(len(row.text) <= 600 for row in rows)
    assert all("<" not in row.text and "hidden" not in row.text for row in rows)
    assert "&" in rows[0].text


def test_filings_filter_by_acceptance_not_report_date():
    adapter = Mock()
    adapter.submissions.return_value = {
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K", "4"],
                "acceptanceDateTime": [
                    "2026-07-10T20:00:00Z",
                    "2026-05-01T10:00:00Z",
                    "2026-07-10T10:00:00Z",
                ],
                "accessionNumber": ["0001-26-000002", "old", "other"],
                "primaryDocument": ["report.htm", "old.htm", "other.htm"],
            }
        }
    }
    adapter.document.return_value = "<p>Revenue increased</p><p>Supplier risk</p><p>Guidance unchanged</p>"
    rows = fetch_filings(
        [{"ticker": "AAPL.US", "name": "Apple"}],
        adapter,
        date(2026, 6, 1),
        date(2026, 11, 8),
        pause=lambda _: None,
    )
    assert len(rows) == 1 and len(rows[0].passages) == 3
    assert rows[0].available_at == "2026-07-13T16:30:00+01:00"
    adapter.document.assert_called_once_with(
        "https://www.sec.gov/Archives/edgar/data/320193/000126000002/report.htm"
    )


def test_earnings_past_only_deduped_and_no_uk_calls():
    adapter = Mock()
    adapter.earnings_calendar.return_value = [
        {"date": "2026-07-01"},
        {"date": "2026-07-01"},
        {"date": "2027-01-01"},
    ]
    rows = fetch_earnings(
        [{"ticker": "AAPL.US"}, {"ticker": "AZN.LSE"}], adapter, date(2026, 11, 8), pause=lambda _: None
    )
    assert rows == [{"ticker": "AAPL.US", "date": "2026-07-01", "source": "finnhub"}]
    adapter.earnings_calendar.assert_called_once_with("2023-01-01", "2026-11-08", "AAPL")


def test_step_writes_only_selected_text_file(tmp_path, monkeypatch):
    import scripts.fetch_text as module

    prices = tmp_path / "prices_daily.parquet"
    prices.write_bytes(b"untouched")
    monkeypatch.setattr(
        module, "get_settings", lambda: SimpleNamespace(finnhub_api_key="fake", eodhd_api_key="fake")
    )
    monkeypatch.setattr(
        module,
        "fetch_earnings",
        lambda *args: [{"ticker": "AAPL.US", "date": "2026-07-01", "source": "finnhub"}],
    )
    module.run_step("earnings", tmp_path, date(2026, 11, 8))
    assert prices.read_bytes() == b"untouched"
    assert (tmp_path / "earnings.jsonl").read_text(encoding="utf-8").endswith("\n")
    assert not (tmp_path / "news.jsonl").exists()


def test_hook_errors_do_not_leak_request_credentials(monkeypatch):
    import httpx

    import scripts.fetch_text as module

    def fail(*args):
        raise httpx.RequestError("https://example.test?api_token=secret")

    monkeypatch.setattr(module, "_run_step", fail)
    with pytest.raises(RuntimeError) as error:
        module.run_step("news", "unused")
    assert "secret" not in str(error.value)
    assert error.value.__suppress_context__
