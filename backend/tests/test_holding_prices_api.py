from fastapi.testclient import TestClient

from app.main import app


def test_holding_prices_are_bounded_by_the_active_clock(state, monkeypatch):
    state.clock.set("2026-07-10")
    monkeypatch.setattr(app.state, "app", state, raising=False)
    client = TestClient(app)
    response = client.get("/api/portfolio/holdings/VUAG.LSE/prices?limit=3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "VUAG.LSE" and payload["as_of"] == "2026-07-10"
    expected = state.gw.prices(["VUAG.LSE"])["VUAG.LSE"].dropna().tail(3)
    assert payload["points"] == [
        {"date": date.date().isoformat(), "close_gbp": float(close)} for date, close in expected.items()
    ]
    assert all(point["date"] <= payload["as_of"] for point in payload["points"])
    assert client.get("/api/portfolio/holdings/NOT-A-HOLDING/prices").status_code == 404
    assert client.get("/api/portfolio/holdings/VUAG.LSE/prices?limit=261").status_code == 422
