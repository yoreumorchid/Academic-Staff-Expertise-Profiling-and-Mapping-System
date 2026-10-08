"""Response mappers shared by the profile route modules."""
from __future__ import annotations

from app.db.models import Publication, UserExpertiseTag
from app.schemas import ExpertiseTagOut, PublicationOut, UserExpertiseTagOut


def publication_to_out(publication: Publication) -> PublicationOut:
    return PublicationOut(
        id=publication.id,
        doi=publication.doi,
        title=publication.title,
        venue=publication.venue,
        publication_year=publication.publication_year,
        abstract_missing=publication.abstract_missing,
        abstract_text=(
            publication.abstract.abstract_text if publication.abstract else None
        ),
    )


def expertise_link_to_out(link: UserExpertiseTag) -> UserExpertiseTagOut:
    return UserExpertiseTagOut(
        id=link.id,
        tag=ExpertiseTagOut.model_validate(link.tag),
        confidence=link.confidence,
        source=link.source,
        validated=link.validated,
    )
