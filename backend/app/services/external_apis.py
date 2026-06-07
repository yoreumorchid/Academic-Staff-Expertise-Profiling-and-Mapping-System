"""HTTP clients for the external academic data providers.

These wrappers enforce instructions.md §4 rule 4: every outbound request
is guarded by a retry policy and surfaces an ``ExternalServiceError`` on
exhaustion, which the global exception handler translates into a clean
``503 Service Unavailable`` payload.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_RETRY_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    service_label: str,
    **kwargs: Any,
) -> httpx.Response:
    """Execute ``method url`` with exponential backoff."""
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, max=4),
            retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
    except RetryError as exc:
        raise ExternalServiceError(
            f"{service_label} did not respond after multiple attempts."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(
            f"{service_label} returned HTTP {exc.response.status_code}.",
            details={"status_code": exc.response.status_code},
        ) from exc
    except _RETRY_EXCEPTIONS as exc:
        raise ExternalServiceError(f"{service_label} is unreachable.") from exc
    raise ExternalServiceError(f"{service_label} request failed.")  # pragma: no cover


# ---------------------------------------------------------------------------
# ORCID public API (UC-8 step 1/2, UC-12)
# ---------------------------------------------------------------------------


class OrcidClient:
    """Fetch the DOI list authored by a given ORCID identifier."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def fetch_doi_list(self, orcid_id: str) -> List[str]:
        url = f"{self._settings.orcid_api_base}/{orcid_id}/works"
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await _request_with_retry(
                client, "GET", url, service_label="ORCID", headers=headers
            )
        payload = response.json()
        dois: List[str] = []
        for group in payload.get("group", []):
            for ext_id in group.get("external-ids", {}).get("external-id", []):
                if ext_id.get("external-id-type") == "doi":
                    value = ext_id.get("external-id-value")
                    if value:
                        dois.append(value.strip())
        return list(dict.fromkeys(dois))  # de-dupe, preserve order.


# ---------------------------------------------------------------------------
# OpenAlex API (UC-8 step 3/4)
# ---------------------------------------------------------------------------


class OpenAlexClient:
    """Resolve DOI metadata (title, year, abstract inverted index)."""

    def __init__(self) -> None:
        self._settings = get_settings()

    @staticmethod
    def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
        """Rebuild full abstract text from OpenAlex inverted index."""
        if not inverted_index:
            return None
        position_to_word: Dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                position_to_word[pos] = word
        if not position_to_word:
            return None
        ordered = [position_to_word[idx] for idx in sorted(position_to_word)]
        return " ".join(ordered)

    async def fetch_work_by_doi(self, doi: str) -> Dict[str, Any]:
        url = f"{self._settings.openalex_api_base}/works/doi:{doi}"
        params: Dict[str, str] = {}
        if self._settings.openalex_mailto:
            params["mailto"] = self._settings.openalex_mailto
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await _request_with_retry(
                client,
                "GET",
                url,
                service_label="OpenAlex",
                params=params,
                headers={"Accept": "application/json"},
            )
        return response.json()

    async def fetch_author_by_orcid(self, orcid_id: str) -> Optional[str]:
        """Return the short OpenAlex author ID for a given ORCID (e.g. 'A12345678').

        Returns ``None`` when OpenAlex does not have an author record for
        this ORCID rather than raising — the caller should fall back to the
        ORCID DOI-list path.
        """
        url = f"{self._settings.openalex_api_base}/authors"
        params: Dict[str, str] = {"filter": f"orcid:{orcid_id}"}
        if self._settings.openalex_mailto:
            params["mailto"] = self._settings.openalex_mailto
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await _request_with_retry(
                    client, "GET", url, service_label="OpenAlex",
                    params=params, headers={"Accept": "application/json"},
                )
        except ExternalServiceError:
            logger.warning("OpenAlex author lookup failed for ORCID %s", orcid_id)
            return None
        results = response.json().get("results", [])
        if not results:
            return None
        # ID is a full URL like "https://openalex.org/A12345678" — keep short form.
        raw_id = results[0].get("id", "")
        return raw_id.split("/")[-1] or None

    async def fetch_works_by_author(
        self, openalex_author_id: str, *, max_works: int = 1000
    ) -> List[Dict[str, Any]]:
        """Return all works attributed to an OpenAlex author using cursor pagination.

        Stops after *max_works* to guard against unusually large profiles.
        Each returned dict has the same shape as ``fetch_work_by_doi`` output.
        """
        url = f"{self._settings.openalex_api_base}/works"
        all_works: List[Dict[str, Any]] = []
        cursor: Optional[str] = "*"
        while cursor and len(all_works) < max_works:
            params: Dict[str, str] = {
                "filter": f"authorships.author.id:{openalex_author_id}",
                "per_page": "200",
                "cursor": cursor,
            }
            if self._settings.openalex_mailto:
                params["mailto"] = self._settings.openalex_mailto
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await _request_with_retry(
                    client, "GET", url, service_label="OpenAlex",
                    params=params, headers={"Accept": "application/json"},
                )
            data = response.json()
            all_works.extend(data.get("results", []))
            cursor = (data.get("meta") or {}).get("next_cursor")
        return all_works


# ---------------------------------------------------------------------------
# IEEE Xplore API (UC-15)
# ---------------------------------------------------------------------------


class IeeeXploreClient:
    """Retrieve global research-frontier metadata for benchmarking."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def search(self, query: str, *, max_records: int = 25) -> Dict[str, Any]:
        if not self._settings.ieee_xplore_api_key:
            raise ExternalServiceError(
                "IEEE Xplore API key is not configured.",
                details={"setting": "IEEE_XPLORE_API_KEY"},
            )
        params = {
            "apikey": self._settings.ieee_xplore_api_key,
            "querytext": query,
            "max_records": str(max_records),
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await _request_with_retry(
                client,
                "GET",
                self._settings.ieee_xplore_api_base,
                service_label="IEEE Xplore",
                params=params,
            )
        return response.json()
