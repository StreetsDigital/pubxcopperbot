"""Tests for Copper CRM API client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from copper_client import CopperClient


@pytest.fixture
def copper_client():
    """Create a CopperClient instance for testing."""
    with patch('copper_client.Config') as mock_config:
        mock_config.COPPER_BASE_URL = "https://api.copper.com/developer_api/v1"
        mock_config.COPPER_API_KEY = "test_key"
        mock_config.COPPER_USER_EMAIL = "test@example.com"
        return CopperClient()


class TestCopperClientSearch:
    """Test search operations."""

    @patch('copper_client.requests.request')
    def test_search_people_success(self, mock_request, copper_client):
        """Test successful people search."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": 1, "name": "John Doe", "emails": [{"email": "john@example.com"}]}
        ]
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        results = copper_client.search_people({"name": "John"})

        assert len(results) == 1
        assert results[0]["name"] == "John Doe"
        mock_request.assert_called_once()

    @patch('copper_client.requests.request')
    def test_search_companies_success(self, mock_request, copper_client):
        """Test successful company search."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": 1, "name": "Acme Corp"}
        ]
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        results = copper_client.search_companies({"name": "Acme"})

        assert len(results) == 1
        assert results[0]["name"] == "Acme Corp"

    @patch('copper_client.requests.request')
    def test_search_rate_limit(self, mock_request, copper_client):
        """Test rate limit handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_request.return_value = mock_response

        results = copper_client.search_people({"name": "Test"})

        assert len(results) == 0


class TestCopperClientCreate:
    """Test create operations."""

    @patch('copper_client.requests.request')
    def test_create_person_success(self, mock_request, copper_client):
        """Test successful person creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "New Person",
            "emails": [{"email": "new@example.com"}]
        }
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        data = {"name": "New Person", "emails": [{"email": "new@example.com"}]}
        result = copper_client.create_person(data)

        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "New Person"

    @patch('copper_client.requests.request')
    def test_create_company_success(self, mock_request, copper_client):
        """Test successful company creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 456,
            "name": "New Company"
        }
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        data = {"name": "New Company"}
        result = copper_client.create_company(data)

        assert result is not None
        assert result["id"] == 456


class TestCopperClientUpdate:
    """Test update operations."""

    @patch('copper_client.requests.request')
    def test_update_person_success(self, mock_request, copper_client):
        """Test successful person update."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "Updated Person",
            "emails": [{"email": "updated@example.com"}]
        }
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        updates = {"emails": [{"email": "updated@example.com"}]}
        result = copper_client.update_person(123, updates)

        assert result is not None
        assert result["emails"][0]["email"] == "updated@example.com"


class TestCopperClientDelete:
    """Test delete operations."""

    @patch('copper_client.requests.request')
    def test_delete_person_success(self, mock_request, copper_client):
        """Test successful person deletion."""
        mock_response = Mock()
        mock_response.content = b''
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = copper_client.delete_person(123)

        assert result is True

    @patch('copper_client.requests.request')
    def test_delete_company_success(self, mock_request, copper_client):
        """Test successful company deletion."""
        mock_response = Mock()
        mock_response.content = b''
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = copper_client.delete_company(456)

        assert result is True


class TestCopperClientGet:
    """Test get individual record operations."""

    @patch('copper_client.requests.request')
    def test_get_person_success(self, mock_request, copper_client):
        """Test get person by ID."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "John Doe"
        }
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = copper_client.get_person(123)

        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "John Doe"
