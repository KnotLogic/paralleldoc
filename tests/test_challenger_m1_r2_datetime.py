"""
Adversarial Stress-Test Suite for RFC 3339 Date-Time Validation.
ParallelDoc 3.0 (Milestone 1-r2) — Empirical Verification by Challenger M1-r2-1.

Empirical verification target:
- src/validator.py (check_datetime, get_default_format_checker, IntegrityEngine)
- tests/conftest.py (format_checker fixture)

Objectives:
1. Aggressive edge cases: naive datetimes, date-only, space-separated, invalid months,
   leap seconds, negative offsets, UTC Z, calendar day bounds, leap years, subseconds.
2. Confirm that VULN-M1-01 is completely and definitively resolved.
3. End-to-end document schema integration and format checker registration.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, List
import pytest

import jsonschema
from jsonschema import Draft202012Validator

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from validator import (
    IntegrityEngine,
    check_datetime,
    get_default_format_checker,
    IssueSeverity,
)


# ---------------------------------------------------------------------------
# Test Data Matrices
# ---------------------------------------------------------------------------

VULN_M1_01_NAIVE_VECTORS = [
    ("2026-09-06T17:00:00", "Standard naive ISO datetime without offset"),
    ("2026-09-06T00:00:00", "Midnight naive ISO datetime without offset"),
    ("2026-09-06T23:59:59", "End-of-day naive ISO datetime without offset"),
    ("2026-09-06T17:00:00.000", "Naive datetime with millisecond subseconds"),
    ("2026-09-06T17:00:00.123456", "Naive datetime with microsecond subseconds"),
    ("1999-12-31T23:59:59", "Historical naive ISO datetime"),
    ("2038-01-19T03:14:07", "Y2038 naive ISO datetime"),
]

DATE_ONLY_VECTORS = [
    ("2026-09-06", "Standard ISO date only"),
    ("2026-01-01", "New year date only"),
    ("2026-12-31", "Year end date only"),
    ("2026", "Year only"),
    ("2026-09", "Year and month only"),
    ("2026-09-06T", "Date with trailing T but no time or offset"),
    ("2026-09-06T17:00", "Missing seconds component"),
    ("2026-09-06T17:00Z", "Missing seconds component with Z"),
    ("17:00:00Z", "Time only with Z"),
    ("17:00:00+00:00", "Time only with offset"),
]

SPACE_SEPARATED_VECTORS = [
    ("2026-09-06 17:00:00", "Space separator naive"),
    ("2026-09-06 17:00:00Z", "Space separator with UTC Z"),
    ("2026-09-06 17:00:00z", "Space separator with lowercase z"),
    ("2026-09-06 17:00:00+00:00", "Space separator with zero offset"),
    ("2026-09-06 17:00:00-05:00", "Space separator with negative offset"),
    ("2026-09-06 17:00:00.123Z", "Space separator with subseconds and Z"),
]

INVALID_MONTH_VECTORS = [
    ("2026-00-01T12:00:00Z", "Month 00"),
    ("2026-13-01T12:00:00Z", "Month 13"),
    ("2026-99-01T12:00:00Z", "Month 99"),
    ("2026-0-01T12:00:00Z", "Single digit month 0"),
    ("2026-1-01T12:00:00Z", "Single digit month 1"),
]

LEAP_SECOND_VECTORS = [
    ("2026-12-31T23:59:60Z", "Leap second 60 UTC Z"),
    ("2026-06-30T23:59:60Z", "Mid-year leap second 60 UTC Z"),
    ("2026-12-31T23:59:60+00:00", "Leap second 60 with +00:00 offset"),
    ("2026-12-31T23:59:60-05:00", "Leap second 60 with negative offset"),
    ("2026-12-31T23:59:60.500Z", "Leap second 60 with fractional seconds"),
    ("2026-12-31T23:59:61Z", "Second 61 out of bounds"),
]

VALID_NEGATIVE_OFFSET_VECTORS = [
    ("2026-09-06T17:00:00-00:00", "Negative zero offset (RFC 3339 Section 4.3)"),
    ("2026-09-06T17:00:00-05:00", "US Eastern Standard Time offset (-05:00)"),
    ("2026-09-06T17:00:00-08:00", "US Pacific Standard Time offset (-08:00)"),
    ("2026-09-06T17:00:00-12:00", "Baker Island time offset (-12:00, max negative standard)"),
    ("2026-09-06T17:00:00-03:30", "Newfoundland fractional half-hour offset (-03:30)"),
    ("2026-09-06T17:00:00-09:30", "Marquesas Islands fractional offset (-09:30)"),
    ("2026-09-06T17:00:00-23:59", "Theoretical maximum negative offset (-23:59)"),
    ("2026-09-06T17:00:00.123456-07:00", "Negative offset with microsecond resolution"),
]

VALID_UTC_Z_VECTORS = [
    ("2026-09-06T17:00:00Z", "Standard uppercase UTC Z"),
    ("2026-09-06T17:00:00z", "Lowercase UTC z"),
    ("2026-09-06t17:00:00Z", "Lowercase t separator with uppercase Z"),
    ("2026-09-06t17:00:00z", "All lowercase t and z"),
    ("2026-09-06T00:00:00Z", "Midnight UTC Z"),
    ("2026-09-06T23:59:59Z", "End of day UTC Z"),
    ("2026-09-06T17:00:00.1Z", "1-digit fractional seconds with Z"),
    ("2026-09-06T17:00:00.12Z", "2-digit fractional seconds with Z"),
    ("2026-09-06T17:00:00.123Z", "3-digit millisecond fractional seconds with Z"),
    ("2026-09-06T17:00:00.123456Z", "6-digit microsecond fractional seconds with Z"),
    ("2026-09-06T17:00:00.123456789Z", "9-digit nanosecond fractional seconds with Z"),
]

VALID_POSITIVE_OFFSET_VECTORS = [
    ("2026-09-06T17:00:00+00:00", "Explicit positive zero offset (+00:00)"),
    ("2026-09-06T17:00:00+02:00", "Eastern European Time (+02:00)"),
    ("2026-09-06T17:00:00+03:00", "Kyiv/Moscow summer time (+03:00)"),
    ("2026-09-06T17:00:00+05:30", "India Standard Time fractional (+05:30)"),
    ("2026-09-06T17:00:00+05:45", "Nepal Standard Time fractional (+05:45)"),
    ("2026-09-06T17:00:00+14:00", "Line Islands maximum positive offset (+14:00)"),
    ("2026-09-06T17:00:00+23:59", "Theoretical maximum positive offset (+23:59)"),
    ("2026-09-06T17:00:00.999+12:00", "Positive offset with millisecond fraction"),
]

CALENDAR_DAY_EDGE_CASES = [
    # Invalid 31st day for 30-day months
    ("2026-04-31T12:00:00Z", "April has 30 days, 31 is invalid", False),
    ("2026-06-31T12:00:00Z", "June has 30 days, 31 is invalid", False),
    ("2026-09-31T12:00:00Z", "September has 30 days, 31 is invalid", False),
    ("2026-11-31T12:00:00Z", "November has 30 days, 31 is invalid", False),
    # Valid 31st day for 31-day months
    ("2026-01-31T12:00:00Z", "January 31 is valid", True),
    ("2026-03-31T12:00:00Z", "March 31 is valid", True),
    ("2026-05-31T12:00:00Z", "May 31 is valid", True),
    ("2026-07-31T12:00:00Z", "July 31 is valid", True),
    ("2026-08-31T12:00:00Z", "August 31 is valid", True),
    ("2026-10-31T12:00:00Z", "October 31 is valid", True),
    ("2026-12-31T12:00:00Z", "December 31 is valid", True),
    # Leap year February tests
    ("2024-02-29T12:00:00Z", "2024 is leap year: Feb 29 is valid", True),
    ("2000-02-29T12:00:00Z", "2000 is 400-yr leap year: Feb 29 is valid", True),
    ("2025-02-29T12:00:00Z", "2025 is non-leap: Feb 29 is invalid", False),
    ("1900-02-29T12:00:00Z", "1900 is 100-yr non-leap: Feb 29 is invalid", False),
    ("2024-02-30T12:00:00Z", "Feb 30 is always invalid", False),
    # Day bounds
    ("2026-09-00T12:00:00Z", "Day 00 is invalid", False),
    ("2026-09-32T12:00:00Z", "Day 32 is invalid", False),
    ("2026-09-01T12:00:00Z", "Day 01 is valid", True),
    ("2026-09-30T12:00:00Z", "Day 30 is valid", True),
]

MALFORMED_OFFSET_VECTORS = [
    ("2026-09-06T17:00:00+03", "Missing offset minutes"),
    ("2026-09-06T17:00:00-05", "Negative missing offset minutes"),
    ("2026-09-06T17:00:00+0300", "Military offset without colon"),
    ("2026-09-06T17:00:00-0500", "Negative military offset without colon"),
    ("2026-09-06T17:00:00+24:00", "Offset hour 24 exceeds 23"),
    ("2026-09-06T17:00:00-24:00", "Negative offset hour 24 exceeds 23"),
    ("2026-09-06T17:00:00+99:00", "Offset hour 99 out of bounds"),
    ("2026-09-06T17:00:00+03:60", "Offset minute 60 out of bounds"),
    ("2026-09-06T17:00:00+03:99", "Offset minute 99 out of bounds"),
    ("2026-09-06T17:00:00+0:00", "Single digit offset hour"),
    ("2026-09-06T17:00:00+03:0", "Single digit offset minute"),
    ("2026-09-06T17:00:00+", "Sign only offset"),
    ("2026-09-06T17:00:00-", "Minus only offset"),
    ("2026-09-06T17:00:0003:00", "Missing offset sign"),
    ("2026-09-06T17:00:00+-03:00", "Double sign in offset"),
]

INJECTION_AND_GARBAGE_VECTORS = [
    ("", "Empty string"),
    ("   ", "Whitespace only"),
    ("not-a-datetime", "Arbitrary non-date string"),
    ("2026-09-06T17:00:00Z\n", "Trailing newline"),
    (" 2026-09-06T17:00:00Z", "Leading space"),
    ("2026-09-06T17:00:00Z ", "Trailing space"),
    ("\t2026-09-06T17:00:00Z", "Leading tab"),
    ("2026-09-06T17:00:00Z\x00", "Embedded null byte"),
    ("2026-09-06T17:00:00Zextra", "Trailing alphanumeric characters"),
    ("prefix2026-09-06T17:00:00Z", "Leading prefix characters"),
    ("2026-09-06T17:00:00Z2026-09-06T17:00:00Z", "Concatenated date-time strings"),
    ("2026-09-06T17:00:00Z'; DROP TABLE units;--", "SQL injection vector"),
    ("<script>alert(1)</script>", "XSS payload"),
    ("2026-09-06T17:00:00.Z", "Fractional dot without digits"),
    ("2026-09-06T24:00:00Z", "Hour 24 out of bounds"),
    ("2026-09-06T-1:00:00Z", "Negative hour"),
    ("2026-09-06T17:60:00Z", "Minute 60 out of bounds"),
    ("0000-01-01T00:00:00Z", "Year 0000 out of Python range"),
    ("-2026-01-01T00:00:00Z", "Negative year"),
    ("20260-01-01T00:00:00Z", "Five digit year"),
]


# ===========================================================================
# Test Classes
# ===========================================================================

class TestEmpiricalDatetimeChallenger:
    """Rigorous empirical test suite executed by Challenger M1-r2-1."""

    # -----------------------------------------------------------------------
    # 1. Direct function check_datetime() stress tests
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("vector,desc", VULN_M1_01_NAIVE_VECTORS)
    def test_direct_rejects_vuln_m1_01_naive(self, vector: str, desc: str):
        """VULN-M1-01 check: check_datetime must reject naive datetimes without offset."""
        result = check_datetime(vector)
        assert result is False, f"VULN-M1-01 REPRODUCED: check_datetime accepted naive vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", DATE_ONLY_VECTORS)
    def test_direct_rejects_date_only(self, vector: str, desc: str):
        """Must reject date-only strings or truncated datetimes lacking time/offset."""
        result = check_datetime(vector)
        assert result is False, f"check_datetime accepted date-only vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", SPACE_SEPARATED_VECTORS)
    def test_direct_rejects_space_separated(self, vector: str, desc: str):
        """Must reject space-separated datetimes (RFC 3339 Section 5.6 requires T separator)."""
        result = check_datetime(vector)
        assert result is False, f"check_datetime accepted space-separated vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", INVALID_MONTH_VECTORS)
    def test_direct_rejects_invalid_months(self, vector: str, desc: str):
        """Must reject datetimes with invalid month values (00, 13, 99)."""
        result = check_datetime(vector)
        assert result is False, f"check_datetime accepted invalid month vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", LEAP_SECOND_VECTORS)
    def test_direct_rejects_leap_seconds(self, vector: str, desc: str):
        """Must reject leap seconds (:60) as Python standard library datetime does not support them."""
        result = check_datetime(vector)
        assert result is False, f"check_datetime accepted leap second vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", VALID_NEGATIVE_OFFSET_VECTORS)
    def test_direct_accepts_valid_negative_offsets(self, vector: str, desc: str):
        """Must accept RFC 3339 datetimes with valid negative offsets."""
        result = check_datetime(vector)
        assert result is True, f"check_datetime rejected valid negative offset vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", VALID_UTC_Z_VECTORS)
    def test_direct_accepts_valid_utc_z(self, vector: str, desc: str):
        """Must accept RFC 3339 datetimes with valid UTC Z (both uppercase and lowercase)."""
        result = check_datetime(vector)
        assert result is True, f"check_datetime rejected valid UTC Z vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", VALID_POSITIVE_OFFSET_VECTORS)
    def test_direct_accepts_valid_positive_offsets(self, vector: str, desc: str):
        """Must accept RFC 3339 datetimes with valid positive offsets."""
        result = check_datetime(vector)
        assert result is True, f"check_datetime rejected valid positive offset vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc,expected", CALENDAR_DAY_EDGE_CASES)
    def test_direct_calendar_day_bounds(self, vector: str, desc: str, expected: bool):
        """Must enforce calendar day bounds (30-day months, Feb 29 in leap vs non-leap years)."""
        result = check_datetime(vector)
        assert result is expected, (
            f"Calendar day check failed for '{vector}' ({desc}): expected {expected}, got {result}"
        )

    @pytest.mark.parametrize("vector,desc", MALFORMED_OFFSET_VECTORS)
    def test_direct_rejects_malformed_offsets(self, vector: str, desc: str):
        """Must reject malformed timezone offsets."""
        result = check_datetime(vector)
        assert result is False, f"check_datetime accepted malformed offset vector '{vector}' ({desc})"

    @pytest.mark.parametrize("vector,desc", INJECTION_AND_GARBAGE_VECTORS)
    def test_direct_rejects_injection_and_garbage(self, vector: str, desc: str):
        """Must reject strings with garbage, injection payloads, or out-of-bounds times."""
        result = check_datetime(vector)
        assert result is False, f"check_datetime accepted invalid vector '{vector}' ({desc})"

    def test_direct_non_string_types_passthrough(self):
        """Non-string types return True from format checker (schema type handles type safety)."""
        assert check_datetime(None) is True
        assert check_datetime(12345) is True
        assert check_datetime(["2026-09-06T17:00:00Z"]) is True
        assert check_datetime({"created_at": "2026-09-06T17:00:00Z"}) is True

    # -----------------------------------------------------------------------
    # 2. FormatChecker fixture from tests/conftest.py
    # -----------------------------------------------------------------------

    def test_conftest_format_checker_registration(self, format_checker: jsonschema.FormatChecker):
        """Verify format_checker registered in tests/conftest.py uses strict check_datetime."""
        assert format_checker is not None
        assert "date-time" in format_checker.checkers
        fn = format_checker.checkers["date-time"][0]

        # Must reject naive
        assert fn("2026-09-06T17:00:00") is False, "conftest format_checker accepted naive datetime"
        # Must reject date only
        assert fn("2026-09-06") is False, "conftest format_checker accepted date-only"
        # Must reject space separated
        assert fn("2026-09-06 17:00:00Z") is False, "conftest format_checker accepted space-separated"
        # Must reject leap second
        assert fn("2026-12-31T23:59:60Z") is False, "conftest format_checker accepted leap second"
        # Must reject invalid month
        assert fn("2026-13-01T12:00:00Z") is False, "conftest format_checker accepted month 13"
        # Must accept valid UTC Z
        assert fn("2026-09-06T17:00:00Z") is True, "conftest format_checker rejected valid UTC Z"
        # Must accept valid negative offset
        assert fn("2026-09-06T17:00:00-05:00") is True, "conftest format_checker rejected negative offset"
        # Must accept valid positive offset
        assert fn("2026-09-06T17:00:00+03:00") is True, "conftest format_checker rejected positive offset"

    # -----------------------------------------------------------------------
    # 3. get_default_format_checker() from src/validator.py
    # -----------------------------------------------------------------------

    def test_validator_default_format_checker_registration(self):
        """Verify get_default_format_checker() in src/validator.py enforces strict RFC 3339."""
        checker = get_default_format_checker()
        assert checker is not None
        assert "date-time" in checker.checkers
        fn = checker.checkers["date-time"][0]

        # Check critical vectors
        assert fn("2026-09-06T17:00:00") is False
        assert fn("2026-09-06") is False
        assert fn("2026-09-06 17:00:00") is False
        assert fn("2026-09-06T17:00:00Z") is True
        assert fn("2026-09-06T17:00:00-08:00") is True

    # -----------------------------------------------------------------------
    # 4. Draft202012Validator schema-level enforcement on metadata.created_at
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("vector,desc", VULN_M1_01_NAIVE_VECTORS)
    def test_schema_validator_rejects_vuln_m1_01_naive(
        self,
        vector: str,
        desc: str,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        schema_v3_dict: Dict[str, Any],
    ):
        """Draft202012Validator with default format checker must fail schema validation on naive."""
        checker = get_default_format_checker()
        validator = Draft202012Validator(schema_v3_dict, format_checker=checker)
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = vector
        errors = list(validator.iter_errors(doc))
        assert len(errors) > 0, f"Schema validation passed for naive datetime '{vector}' ({desc})"
        assert any(e.validator == "format" for e in errors), (
            f"Expected 'format' validator error for '{vector}', got: {[e.validator for e in errors]}"
        )

    @pytest.mark.parametrize("vector,desc", DATE_ONLY_VECTORS)
    def test_schema_validator_rejects_date_only(
        self,
        vector: str,
        desc: str,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        schema_v3_dict: Dict[str, Any],
    ):
        """Draft202012Validator must fail schema validation on date-only / truncated."""
        checker = get_default_format_checker()
        validator = Draft202012Validator(schema_v3_dict, format_checker=checker)
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = vector
        errors = list(validator.iter_errors(doc))
        assert len(errors) > 0, f"Schema validation passed for date-only '{vector}' ({desc})"
        assert any(e.validator == "format" for e in errors)

    @pytest.mark.parametrize("vector,desc", SPACE_SEPARATED_VECTORS)
    def test_schema_validator_rejects_space_separated(
        self,
        vector: str,
        desc: str,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        schema_v3_dict: Dict[str, Any],
    ):
        """Draft202012Validator must fail schema validation on space-separated."""
        checker = get_default_format_checker()
        validator = Draft202012Validator(schema_v3_dict, format_checker=checker)
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = vector
        errors = list(validator.iter_errors(doc))
        assert len(errors) > 0, f"Schema validation passed for space-separated '{vector}' ({desc})"
        assert any(e.validator == "format" for e in errors)

    @pytest.mark.parametrize("vector,desc", VALID_UTC_Z_VECTORS)
    def test_schema_validator_accepts_valid_utc_z(
        self,
        vector: str,
        desc: str,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        schema_v3_dict: Dict[str, Any],
    ):
        """Draft202012Validator must pass valid UTC Z datetimes."""
        checker = get_default_format_checker()
        validator = Draft202012Validator(schema_v3_dict, format_checker=checker)
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = vector
        errors = list(validator.iter_errors(doc))
        assert len(errors) == 0, f"Valid UTC Z vector rejected: '{vector}' ({desc}), errors: {errors}"

    @pytest.mark.parametrize("vector,desc", VALID_NEGATIVE_OFFSET_VECTORS)
    def test_schema_validator_accepts_valid_negative_offsets(
        self,
        vector: str,
        desc: str,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        schema_v3_dict: Dict[str, Any],
    ):
        """Draft202012Validator must pass valid negative offset datetimes."""
        checker = get_default_format_checker()
        validator = Draft202012Validator(schema_v3_dict, format_checker=checker)
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = vector
        errors = list(validator.iter_errors(doc))
        assert len(errors) == 0, f"Valid negative offset vector rejected: '{vector}' ({desc}), errors: {errors}"

    # -----------------------------------------------------------------------
    # 5. IntegrityEngine end-to-end validate_document() integration
    # -----------------------------------------------------------------------

    def test_integrity_engine_end_to_end_rejects_vuln_m1_01(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
    ):
        """IntegrityEngine.validate_document must mark doc invalid and report ERR_SCHEMA_V3_VIOLATION."""
        engine = IntegrityEngine()
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = "2026-09-06T17:00:00"  # VULN-M1-01 vector

        report = engine.validate_document(doc)
        assert report.is_valid is False, "IntegrityEngine reported is_valid=True for naive datetime!"
        assert report.structure_state == "invalid"
        format_issues = [
            issue for issue in report.issues
            if issue.code == "ERR_SCHEMA_V3_VIOLATION" and issue.context.get("validator") == "format"
        ]
        assert len(format_issues) >= 1, (
            f"Expected ERR_SCHEMA_V3_VIOLATION with validator=format, found: {report.issues}"
        )
        assert format_issues[0].path == "/metadata/created_at"

    def test_integrity_engine_end_to_end_accepts_valid_rfc3339(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
    ):
        """IntegrityEngine.validate_document must accept compliant RFC 3339 with offset."""
        engine = IntegrityEngine()
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = "2026-09-06T17:00:00.123456+03:00"

        report = engine.validate_document(doc)
        assert report.is_valid is True, f"IntegrityEngine rejected valid datetime: {report.issues}"
        assert report.structure_state == "valid"
        assert len(report.issues) == 0
