"""Regression tests for the verified instrument catalogue (#5)."""


def _valid_isin(isin: str) -> bool:
    """Validate an ISIN using its MOD-10 check digit."""
    expanded = "".join(str(ord(char) - 55) if char.isalpha() else char for char in isin)
    digits = [int(char) for char in expanded]
    total = sum(sum(divmod(value * (2 if index % 2 == 1 else 1), 10))
                for index, value in enumerate(reversed(digits)))
    return total % 10 == 0


def test_catalogue_is_verified_and_uses_correct_listing_units(state):
    instruments = state.gw.catalogue(eligible_only=False)

    assert len(instruments) == 18
    assert all(instrument.verified and instrument.isin for instrument in instruments)
    assert all(_valid_isin(instrument.isin) for instrument in instruments if instrument.isin)

    by_ticker = {instrument.ticker: instrument for instrument in instruments}
    assert by_ticker["IGLS.LSE"].quote_unit == "GBP"
    assert by_ticker["INXG.LSE"].quote_unit == "GBP"
    assert by_ticker["SGLN.LSE"].quote_unit == "GBX"
    assert by_ticker["ULVR.LSE"].isin == "GB00BVZK7T90"


def test_vwrp_ocf_is_selected_by_historical_clock(state):
    vwrp = lambda: next(item for item in state.gw.catalogue() if item.ticker == "VWRP.LSE")

    state.clock.set("2026-07-07")
    assert vwrp().ocf == 0.0019

    state.clock.set("2026-07-27")
    assert vwrp().ocf == 0.0019

    state.clock.set("2026-07-28")
    assert vwrp().ocf == 0.0014
