"""SEC EDGAR adapter (free). SEC asks for a descriptive User-Agent with a contact (EDGAR_USER_AGENT). Owner: Jin."""
from __future__ import annotations

import httpx


class Edgar:
    def __init__(self, user_agent: str, timeout: float = 30):
        self.client = httpx.Client(timeout=timeout, headers={"User-Agent": user_agent})

    def submissions(self, cik: str) -> dict:
        """cik zero-padded to 10 digits. Returns recent filings with acceptanceDateTime."""
        r = self.client.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
        r.raise_for_status()
        return r.json()

    def document(self, url: str) -> str:
        r = self.client.get(url)
        r.raise_for_status()
        return r.text
