"""Tests for input validation module."""

import pytest
from validation import (
    validate_and_sanitize,
    validate_entity_id,
    _normalize_entity_type,
    _sanitize_value,
)


class TestValidateAndSanitize:
    """Test validate_and_sanitize function."""

    def test_valid_person_create(self):
        """Test valid person data passes validation."""
        data = {
            "name": "John Doe",
            "emails": [{"email": "john@example.com"}],
            "title": "Engineer",
        }
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is True
        assert len(errors) == 0
        assert sanitized["name"] == "John Doe"
        assert sanitized["emails"] == [{"email": "john@example.com"}]

    def test_missing_required_field(self):
        """Test missing required field fails validation."""
        data = {"title": "Engineer"}  # Missing 'name'
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is False
        assert any("name" in e.lower() and "missing" in e.lower() for e in errors)

    def test_disallowed_field_blocked(self):
        """Test disallowed fields are blocked."""
        data = {
            "name": "John Doe",
            "malicious_field": "attack_payload",
            "__proto__": "injection",
        }
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        # Should fail due to disallowed fields
        assert is_valid is False
        assert "malicious_field" not in sanitized
        assert "__proto__" not in sanitized
        assert any("malicious_field" in e for e in errors)

    def test_update_allows_partial_data(self):
        """Test update operation allows partial data (no required fields)."""
        data = {"title": "Senior Engineer"}
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "update")

        assert is_valid is True
        assert sanitized["title"] == "Senior Engineer"

    def test_whitespace_trimmed(self):
        """Test string values have whitespace trimmed."""
        data = {"name": "  John Doe  ", "title": "  Engineer  "}
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is True
        assert sanitized["name"] == "John Doe"
        assert sanitized["title"] == "Engineer"

    def test_invalid_email_format(self):
        """Test invalid email format is rejected."""
        data = {
            "name": "John Doe",
            "emails": [{"email": "not-an-email"}],
        }
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is False
        assert any("email" in e.lower() for e in errors)

    def test_valid_email_format(self):
        """Test valid email format passes."""
        data = {
            "name": "John Doe",
            "emails": [{"email": "john.doe@example.com"}],
        }
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is True

    def test_negative_monetary_value(self):
        """Test negative monetary value is rejected."""
        data = {
            "name": "Big Deal",
            "monetary_value": -1000,
        }
        is_valid, sanitized, errors = validate_and_sanitize(
            "opportunities", data, "create"
        )

        assert is_valid is False
        assert any("negative" in e.lower() for e in errors)

    def test_valid_opportunity(self):
        """Test valid opportunity data."""
        data = {
            "name": "Big Deal",
            "monetary_value": 50000,
            "pipeline_id": 123,
        }
        is_valid, sanitized, errors = validate_and_sanitize(
            "opportunities", data, "create"
        )

        assert is_valid is True
        assert sanitized["monetary_value"] == 50000

    def test_valid_task_with_related_resource(self):
        """Test task with valid related_resource."""
        data = {
            "name": "Follow up call",
            "related_resource": {"type": "person", "id": 123},
        }
        is_valid, sanitized, errors = validate_and_sanitize("tasks", data, "create")

        assert is_valid is True
        assert sanitized["related_resource"]["type"] == "person"

    def test_task_missing_related_resource_type(self):
        """Test task with invalid related_resource fails."""
        data = {
            "name": "Follow up call",
            "related_resource": {"id": 123},  # Missing 'type'
        }
        is_valid, sanitized, errors = validate_and_sanitize("tasks", data, "create")

        assert is_valid is False
        assert any("type" in e.lower() for e in errors)

    def test_unknown_entity_type(self):
        """Test unknown entity type fails."""
        data = {"name": "Test"}
        is_valid, sanitized, errors = validate_and_sanitize("unknown", data, "create")

        assert is_valid is False
        assert any("unknown" in e.lower() for e in errors)

    def test_long_string_truncated(self):
        """Test overly long strings are truncated."""
        data = {"name": "A" * 600}  # Exceeds 500 char limit
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is True
        assert len(sanitized["name"]) == 500

    def test_empty_list_removed(self):
        """Test empty lists are removed from data."""
        data = {"name": "John Doe", "tags": []}
        is_valid, sanitized, errors = validate_and_sanitize("people", data, "create")

        assert is_valid is True
        assert "tags" not in sanitized or sanitized.get("tags") is None


class TestNormalizeEntityType:
    """Test entity type normalization."""

    def test_singular_to_plural(self):
        """Test singular forms are normalized to plural."""
        assert _normalize_entity_type("person") == "people"
        assert _normalize_entity_type("company") == "companies"
        assert _normalize_entity_type("opportunity") == "opportunities"
        assert _normalize_entity_type("lead") == "leads"
        assert _normalize_entity_type("task") == "tasks"
        assert _normalize_entity_type("project") == "projects"

    def test_aliases(self):
        """Test alternative names are normalized."""
        assert _normalize_entity_type("contact") == "people"
        assert _normalize_entity_type("deal") == "opportunities"

    def test_case_insensitive(self):
        """Test normalization is case insensitive."""
        assert _normalize_entity_type("PERSON") == "people"
        assert _normalize_entity_type("Company") == "companies"


class TestSanitizeValue:
    """Test value sanitization."""

    def test_string_trimmed(self):
        """Test strings are trimmed."""
        assert _sanitize_value("name", "  hello  ") == "hello"

    def test_empty_string_returns_none(self):
        """Test empty strings return None."""
        assert _sanitize_value("name", "   ") is None
        assert _sanitize_value("name", "") is None

    def test_list_sanitized(self):
        """Test lists have items sanitized."""
        result = _sanitize_value("tags", ["  tag1  ", "tag2", ""])
        assert result == ["tag1", "tag2"]

    def test_dict_sanitized(self):
        """Test dicts have values sanitized."""
        result = _sanitize_value("address", {"city": "  NYC  ", "empty": ""})
        assert result == {"city": "NYC"}

    def test_none_passthrough(self):
        """Test None values pass through."""
        assert _sanitize_value("name", None) is None

    def test_number_passthrough(self):
        """Test numeric values pass through."""
        assert _sanitize_value("monetary_value", 1000) == 1000
        assert _sanitize_value("value", 3.14) == 3.14

    def test_boolean_passthrough(self):
        """Test boolean values pass through."""
        assert _sanitize_value("active", True) is True
        assert _sanitize_value("active", False) is False


class TestValidateEntityId:
    """Test entity ID validation."""

    def test_valid_integer(self):
        """Test valid integer passes."""
        assert validate_entity_id(123) == 123

    def test_valid_string_number(self):
        """Test string number is converted."""
        assert validate_entity_id("456") == 456

    def test_zero_invalid(self):
        """Test zero is invalid."""
        assert validate_entity_id(0) is None

    def test_negative_invalid(self):
        """Test negative numbers are invalid."""
        assert validate_entity_id(-1) is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert validate_entity_id(None) is None

    def test_non_numeric_string_invalid(self):
        """Test non-numeric strings are invalid."""
        assert validate_entity_id("abc") is None
        assert validate_entity_id("12abc") is None

    def test_float_converted(self):
        """Test float is converted to int."""
        assert validate_entity_id(123.7) == 123
