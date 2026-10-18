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

    def _params(self, **values: str) -> Dict[str, str]:
        params = dict(values)
        if self._settings.openalex_mailto:
            params["mailto"] = self._settings.openalex_mailto
        if self._settings.openalex_api_key:
            params["api_key"] = self._settings.openalex_api_key
        return params

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
        params = self._params()
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
        params = self._params(filter=f"orcid:{orcid_id}")
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
            params = self._params(**{
                "filter": f"authorships.author.id:{openalex_author_id}",
                "per_page": "200",
                "cursor": cursor,
            })
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await _request_with_retry(
                    client, "GET", url, service_label="OpenAlex",
                    params=params, headers={"Accept": "application/json"},
                )
            data = response.json()
            all_works.extend(data.get("results", []))
            cursor = (data.get("meta") or {}).get("next_cursor")
        return all_works

    async def fetch_computer_science_benchmark_topics(
        self, *, topics_per_subfield: int = 2
    ) -> Dict[str, Any]:
        """Return prominent research-output topics across every CS subfield.

        OpenAlex field 17 is Computer Science. For each of its official
        subfields, the Works API groups research outputs by primary topic. The
        grouped ``count`` is therefore the number of article, review, book, or
        book-chapter records whose primary topic is that topic; it is not a
        growth or trend score.
        """
        base = self._settings.openalex_api_base.rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            field_response = await _request_with_retry(
                client,
                "GET",
                f"{base}/fields/17",
                service_label="OpenAlex",
                params=self._params(),
                headers={"Accept": "application/json"},
            )
            field = field_response.json()
            if field.get("display_name") != "Computer Science":
                raise ExternalServiceError(
                    "OpenAlex field 17 did not resolve to Computer Science."
                )

            selected: List[Dict[str, Any]] = []
            for subfield in field.get("subfields", []):
                short_id = str(subfield.get("id", "")).rsplit("/", 1)[-1]
                if not short_id:
                    continue
                source_filter = (
                    f"primary_topic.subfield.id:{short_id},"
                    "type:article|review|book|book-chapter"
                )
                response = await _request_with_retry(
                    client,
                    "GET",
                    f"{base}/works",
                    service_label="OpenAlex",
                    params=self._params(
                        filter=source_filter,
                        group_by="primary_topic.id",
                        per_page=str(topics_per_subfield),
                    ),
                    headers={"Accept": "application/json"},
                )
                for group in response.json().get("group_by", []):
                    topic_id = str(group.get("key", "")).rsplit("/", 1)[-1]
                    if not topic_id:
                        continue
                    selected.append({
                        "id": topic_id,
                        "display_name": group.get("key_display_name") or topic_id,
                        "research_output_count": int(group.get("count") or 0),
                        "subfield_id": short_id,
                        "subfield_name": subfield.get("display_name") or short_id,
                        "source_filter": source_filter,
                    })

            if not selected:
                raise ExternalServiceError(
                    "OpenAlex did not return Computer Science benchmark topics."
                )

            topic_ids = "|".join(item["id"] for item in selected)
            details_response = await _request_with_retry(
                client,
                "GET",
                f"{base}/topics",
                service_label="OpenAlex",
                params=self._params(
                    filter=f"id:{topic_ids}",
                    per_page=str(len(selected)),
                    select=(
                        "id,display_name,description,works_count,cited_by_count,"
                        "subfield,field,updated_date"
                    ),
                ),
                headers={"Accept": "application/json"},
            )

        details = {
            str(item.get("id", "")).rsplit("/", 1)[-1]: item
            for item in details_response.json().get("results", [])
        }
        topics: List[Dict[str, Any]] = []
        for item in selected:
            detail = details.get(item["id"], {})
            topics.append({
                **item,
                "description": detail.get("description"),
                "openalex_works_count": detail.get("works_count"),
                "cited_by_count": detail.get("cited_by_count"),
                "updated_date": detail.get("updated_date"),
            })
        return {
            "field": {
                "id": str(field.get("id", "")).rsplit("/", 1)[-1],
                "display_name": field.get("display_name"),
                "updated_date": field.get("updated_date"),
            },
            "topics": topics,
        }
