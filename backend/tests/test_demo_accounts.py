import pytest
from pydantic import ValidationError

from app.db.models import PortfolioType, UserRole
from app.schemas import RegisterRequest
from app.tools.demo_accounts import (
    _valid_orcid_checksum,
    allocate_academic_emails,
    validate_staff_input,
)


def test_orcid_checksum_validation() -> None:
    assert _valid_orcid_checksum("0000-0002-1825-0097")
    assert _valid_orcid_checksum("0000-0001-5109-3700")
    assert not _valid_orcid_checksum("0000-0002-1825-0098")
    assert not _valid_orcid_checksum("0000-0002-1825-009x")


def test_single_staff_input_is_normalized() -> None:
    account = validate_staff_input(
        "  One   Staff ",
        "0000-0002-1825-0097",
        " Computer   Science ",
        "+60 12-345 6789",
    )
    assert account.full_name == "ONE STAFF"
    assert account.department == "Computer Science"
    assert account.phone_number == "+60 12-345 6789"


def test_single_staff_input_rejects_bad_orcid_checksum() -> None:
    with pytest.raises(ValueError, match="checksum"):
        validate_staff_input(
            "One Staff",
            "0000-0002-1825-0098",
            "Computer Science",
            "+60 12-345 6789",
        )


def test_academic_registration_requires_phone_number() -> None:
    with pytest.raises(ValidationError, match="requires a phone number"):
        RegisterRequest(
            full_name="One Staff",
            email="one.staff@um.edu.my",
            password="Secure1!",
            role=UserRole.ACADEMIC_STAFF,
            department="Computer Science",
            orcid_id="0000-0002-1825-0097",
        )


def test_dual_role_registration_requires_phone_number() -> None:
    with pytest.raises(ValidationError, match="Department and phone number"):
        RegisterRequest(
            full_name="One Admin",
            email="one.admin@um.edu.my",
            password="Secure1!",
            role=UserRole.FACULTY_ADMINISTRATOR,
            department="Computer Science",
            orcid_id="0000-0002-1825-0097",
            portfolio=PortfolioType.FACULTY_MANAGER,
        )


def test_academic_email_numbering_continues_existing_format() -> None:
    assert allocate_academic_emails(
        [
            "faculty_manager@um.edu.my",
            "academic_staff@um.edu.my",
            "academic_staff2@um.edu.my",
            "academic_staff11@um.edu.my",
        ],
        3,
    ) == [
        "academic_staff12@um.edu.my",
        "academic_staff13@um.edu.my",
        "academic_staff14@um.edu.my",
    ]


def test_academic_email_numbering_starts_with_current_base() -> None:
    assert allocate_academic_emails(["faculty_manager@um.edu.my"], 2) == [
        "academic_staff@um.edu.my",
        "academic_staff2@um.edu.my",
    ]
