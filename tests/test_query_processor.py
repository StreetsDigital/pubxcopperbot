"""Tests for query processor."""

import pytest
from unittest.mock import Mock, patch
from query_processor import QueryProcessor


@pytest.fixture
def query_processor():
    """Create a QueryProcessor instance for testing."""
    with patch('query_processor.Config') as mock_config:
        mock_config.OPENAI_API_KEY = None
        return QueryProcessor()


class TestEntityTypeDetermination:
    """Test entity type determination from queries."""

    def test_determine_people_type(self, query_processor):
        """Test determining people entity type."""
        query = "find contacts at Acme Corp"
        entity_type = query_processor._determine_entity_type(query)
        assert entity_type == "people"

    def test_determine_company_type(self, query_processor):
        """Test determining company entity type."""
        query = "show me companies in San Francisco"
        entity_type = query_processor._determine_entity_type(query)
        assert entity_type == "companies"

    def test_determine_opportunity_type(self, query_processor):
        """Test determining opportunity entity type."""
        query = "list opportunities over $50k"
        entity_type = query_processor._determine_entity_type(query)
        assert entity_type == "opportunities"

    def test_determine_lead_type(self, query_processor):
        """Test determining lead entity type."""
        query = "find leads from last week"
        entity_type = query_processor._determine_entity_type(query)
        assert entity_type == "leads"

    def test_determine_task_type(self, query_processor):
        """Test determining task entity type."""
        query = "show me tasks due today"
        entity_type = query_processor._determine_entity_type(query)
        assert entity_type == "tasks"

    def test_determine_project_type(self, query_processor):
        """Test determining project entity type."""
        query = "list all active projects"
        entity_type = query_processor._determine_entity_type(query)
        assert entity_type == "projects"


class TestBasicParsing:
    """Test basic query parsing."""

    def test_parse_email(self, query_processor):
        """Test extracting email from query."""
        query = "find person with email john@example.com"
        result = query_processor._parse_basic(query, "people")

        assert "emails" in result["search_criteria"]
        assert "john@example.com" in result["search_criteria"]["emails"]

    def test_parse_quoted_name(self, query_processor):
        """Test extracting quoted name from query."""
        query = 'find "John Smith"'
        result = query_processor._parse_basic(query, "people")

        assert result["search_criteria"].get("name") == "John Smith"

    def test_parse_location(self, query_processor):
        """Test extracting location from query."""
        query = "find companies in San Francisco"
        result = query_processor._parse_basic(query, "companies")

        assert result["search_criteria"].get("city") == "San Francisco"


class TestResultFormatting:
    """Test result formatting."""

    def test_format_empty_results(self, query_processor):
        """Test formatting empty results."""
        formatted = query_processor.format_results([], "people")
        assert formatted == "No results found."

    def test_format_person_results(self, query_processor):
        """Test formatting person results."""
        results = [
            {
                "name": "John Doe",
                "emails": [{"email": "john@example.com"}],
                "phone_numbers": [{"number": "555-1234"}],
                "company_name": "Acme Corp"
            }
        ]

        formatted = query_processor.format_results(results, "people")

        assert "John Doe" in formatted
        assert "john@example.com" in formatted
        assert "555-1234" in formatted
        assert "Acme Corp" in formatted

    def test_format_company_results(self, query_processor):
        """Test formatting company results."""
        results = [
            {
                "name": "Acme Corp",
                "city": "San Francisco",
                "state": "CA"
            }
        ]

        formatted = query_processor.format_results(results, "companies")

        assert "Acme Corp" in formatted
        assert "San Francisco" in formatted

    def test_format_truncates_long_results(self, query_processor):
        """Test that long result lists are truncated."""
        results = [{"name": f"Person {i}"} for i in range(30)]

        formatted = query_processor.format_results(results, "people")

        assert "Showing first 20" in formatted
