"""Tests for CSV handler."""

import pytest
from unittest.mock import Mock, patch
from csv_handler import CSVHandler


@pytest.fixture
def mock_copper_client():
    """Create a mock Copper client."""
    client = Mock()
    client.search_people.return_value = [{"id": 1, "name": "John Doe"}]
    client.search_companies.return_value = [{"id": 2, "name": "Acme Corp"}]
    client.search_opportunities.return_value = []
    return client


@pytest.fixture
def csv_handler(mock_copper_client):
    """Create a CSVHandler instance for testing."""
    return CSVHandler(mock_copper_client)


class TestCSVParsing:
    """Test CSV parsing functionality."""

    def test_parse_csv_success(self, csv_handler):
        """Test successful CSV parsing."""
        csv_content = b"name,email,company\nJohn Doe,john@example.com,Acme Corp"

        rows = csv_handler.parse_csv(csv_content)

        assert len(rows) == 1
        assert rows[0]["name"] == "John Doe"
        assert rows[0]["email"] == "john@example.com"
        assert rows[0]["company"] == "Acme Corp"

    def test_parse_empty_csv(self, csv_handler):
        """Test parsing empty CSV."""
        csv_content = b"name,email,company\n"

        rows = csv_handler.parse_csv(csv_content)

        assert len(rows) == 0


class TestCSVEnrichment:
    """Test CSV enrichment functionality."""

    def test_check_contact_exists(self, csv_handler):
        """Test checking if contact exists."""
        row = {"name": "John Doe", "email": "john@example.com"}

        exists = csv_handler._check_contact_exists(row)

        assert exists is True

    def test_check_company_exists(self, csv_handler):
        """Test checking if company exists."""
        row = {"company": "Acme Corp"}

        exists = csv_handler._check_company_exists(row)

        assert exists is True

    def test_check_opportunity_not_exists(self, csv_handler):
        """Test checking if opportunity doesn't exist."""
        row = {"opportunity": "Nonexistent Deal"}

        exists = csv_handler._check_opportunity_exists(row)

        assert exists is False

    def test_process_csv_queries(self, csv_handler):
        """Test processing CSV queries."""
        rows = [
            {"name": "John Doe", "email": "john@example.com", "company": "Acme Corp", "opportunity": "Deal 1"}
        ]

        results = csv_handler.process_csv_queries(rows)

        assert results['total_queries'] == 1
        assert results['successful'] == 1
        assert len(results['enriched_rows']) == 1

        enriched = results['enriched_rows'][0]
        assert enriched['Contact is in CRM'] == 'Yes'
        assert enriched['Company is in CRM'] == 'Yes'
        assert enriched['Opportunity exists'] == 'No'

    def test_generate_enriched_csv(self, csv_handler):
        """Test generating enriched CSV."""
        enriched_rows = [
            {
                "name": "John Doe",
                "email": "john@example.com",
                "Contact is in CRM": "Yes",
                "Company is in CRM": "Yes",
                "Opportunity exists": "No"
            }
        ]

        csv_content = csv_handler.generate_enriched_csv(enriched_rows)

        assert csv_content is not None
        assert b"Contact is in CRM" in csv_content
        assert b"Company is in CRM" in csv_content
        assert b"John Doe" in csv_content
