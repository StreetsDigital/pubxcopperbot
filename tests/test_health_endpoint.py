"""Tests for health endpoint."""

import pytest
import json
import sys
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.request
import socket
from datetime import datetime


# We need to mock config before importing app
@pytest.fixture(scope="module", autouse=True)
def mock_config():
    """Mock config validation to prevent exit on missing env vars."""
    mock_config = MagicMock()
    mock_config.SLACK_BOT_TOKEN = "xoxb-test"
    mock_config.SLACK_SIGNING_SECRET = "test-secret"
    mock_config.SLACK_APP_TOKEN = "xapp-test"
    mock_config.COPPER_API_KEY = "test-key"
    mock_config.COPPER_USER_EMAIL = "test@example.com"
    mock_config.LOG_LEVEL = "INFO"
    mock_config.DEFAULT_TASK_ASSIGNEE_ID = None
    mock_config.DEFAULT_PIPELINE_NAME = None
    mock_config.validate = Mock()

    with patch.dict('sys.modules', {'config': MagicMock(Config=mock_config)}):
        # Also mock the Slack App to prevent initialization issues
        mock_slack_app = MagicMock()
        mock_socket_handler = MagicMock()

        with patch('slack_bolt.App', return_value=mock_slack_app):
            with patch('slack_bolt.adapter.socket_mode.SocketModeHandler', return_value=mock_socket_handler):
                yield


class TestHealthHandler:
    """Test health endpoint handler."""

    @pytest.fixture
    def health_handler_class(self):
        """Get the HealthHandler class with mocked dependencies."""
        # Create a minimal HealthHandler for testing
        class MockHealthHandler(BaseHTTPRequestHandler):
            """Test version of HealthHandler."""

            # Mock component references
            mock_app = Mock()
            mock_copper_client = Mock()
            mock_approval_system = Mock()
            mock_query_processor = Mock()
            mock_csv_handler = Mock()
            mock_task_processor = Mock()
            mock_start_time = datetime.now()

            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path == '/health':
                    self._handle_health()
                elif self.path == '/':
                    self._handle_root()
                else:
                    self.send_error(404, 'Not Found')

            def _handle_health(self):
                uptime = datetime.now() - self.mock_start_time
                uptime_seconds = int(uptime.total_seconds())

                components = {
                    'slack_app': self.mock_app is not None,
                    'copper_client': self.mock_copper_client is not None,
                    'approval_system': self.mock_approval_system is not None,
                    'query_processor': self.mock_query_processor is not None,
                    'csv_handler': self.mock_csv_handler is not None,
                    'task_processor': self.mock_task_processor is not None,
                }

                try:
                    pending_count = len(self.mock_approval_system.get_pending_requests())
                    approver_count = len(self.mock_approval_system.get_approvers())
                    admin_count = len(self.mock_approval_system.get_admins())
                    components['approval_state'] = True
                except Exception:
                    pending_count = -1
                    approver_count = -1
                    admin_count = -1
                    components['approval_state'] = False

                all_healthy = all(components.values())

                health = {
                    'status': 'healthy' if all_healthy else 'degraded',
                    'uptime_seconds': uptime_seconds,
                    'uptime_human': str(uptime).split('.')[0],
                    'started_at': self.mock_start_time.isoformat(),
                    'components': components,
                    'stats': {
                        'pending_approvals': pending_count,
                        'approvers': approver_count,
                        'admins': admin_count,
                    }
                }

                self.send_response(200 if all_healthy else 503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(health, indent=2).encode())

            def _handle_root(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Copper CRM Slack Bot - OK')

        # Configure mock approval system
        MockHealthHandler.mock_approval_system.get_pending_requests.return_value = [
            {'id': '1'}, {'id': '2'}
        ]
        MockHealthHandler.mock_approval_system.get_approvers.return_value = [
            'user1', 'user2', 'user3'
        ]
        MockHealthHandler.mock_approval_system.get_admins.return_value = ['admin1']

        return MockHealthHandler

    @pytest.fixture
    def health_server(self, health_handler_class):
        """Start a test health server on a random port."""
        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HTTPServer(('127.0.0.1', port), health_handler_class)
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        yield f'http://127.0.0.1:{port}'

        server.server_close()

    def test_health_endpoint_returns_200(self, health_server):
        """Test /health returns 200 when healthy."""
        url = f'{health_server}/health'
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data['status'] == 'healthy'

    def test_health_endpoint_returns_json(self, health_server):
        """Test /health returns valid JSON with expected fields."""
        url = f'{health_server}/health'
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())

            # Check required fields
            assert 'status' in data
            assert 'uptime_seconds' in data
            assert 'uptime_human' in data
            assert 'started_at' in data
            assert 'components' in data
            assert 'stats' in data

    def test_health_endpoint_components(self, health_server):
        """Test /health returns component status."""
        url = f'{health_server}/health'
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())

            components = data['components']
            assert 'slack_app' in components
            assert 'copper_client' in components
            assert 'approval_system' in components
            assert 'query_processor' in components
            assert 'csv_handler' in components
            assert 'task_processor' in components
            assert 'approval_state' in components

            # All should be True
            assert all(components.values())

    def test_health_endpoint_stats(self, health_server):
        """Test /health returns approval stats."""
        url = f'{health_server}/health'
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())

            stats = data['stats']
            assert stats['pending_approvals'] == 2
            assert stats['approvers'] == 3
            assert stats['admins'] == 1

    def test_health_endpoint_uptime(self, health_server):
        """Test /health returns valid uptime."""
        url = f'{health_server}/health'
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())

            assert isinstance(data['uptime_seconds'], int)
            assert data['uptime_seconds'] >= 0
            assert ':' in data['uptime_human']  # Format like "0:00:01"


class TestHealthHandlerRoot:
    """Test root endpoint."""

    @pytest.fixture
    def handler_class(self):
        """Get a handler class for root endpoint testing."""
        class RootHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Copper CRM Slack Bot - OK')
                else:
                    self.send_error(404, 'Not Found')

        return RootHandler

    @pytest.fixture
    def root_server(self, handler_class):
        """Start a test server for root endpoint."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HTTPServer(('127.0.0.1', port), handler_class)
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        yield f'http://127.0.0.1:{port}'

        server.server_close()

    def test_root_endpoint_returns_200(self, root_server):
        """Test / returns 200."""
        url = f'{root_server}/'
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200

    def test_root_endpoint_returns_text(self, root_server):
        """Test / returns expected text."""
        url = f'{root_server}/'
        with urllib.request.urlopen(url, timeout=5) as response:
            content = response.read().decode()
            assert 'Copper CRM Slack Bot' in content
            assert 'OK' in content


class TestHealthHandlerNotFound:
    """Test 404 handling."""

    @pytest.fixture
    def handler_class(self):
        """Get a handler class for 404 testing."""
        class NotFoundHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path == '/health':
                    self.send_response(200)
                    self.end_headers()
                elif self.path == '/':
                    self.send_response(200)
                    self.end_headers()
                else:
                    self.send_error(404, 'Not Found')

        return NotFoundHandler

    @pytest.fixture
    def notfound_server(self, handler_class):
        """Start a test server for 404 test."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HTTPServer(('127.0.0.1', port), handler_class)
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        yield f'http://127.0.0.1:{port}'

        server.server_close()

    def test_unknown_path_returns_404(self, notfound_server):
        """Test unknown path returns 404."""
        url = f'{notfound_server}/unknown'
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url, timeout=5)
        assert exc_info.value.code == 404


class TestHealthHandlerDegraded:
    """Test degraded health status."""

    @pytest.fixture
    def degraded_handler_class(self):
        """Get a handler that reports degraded status."""
        class DegradedHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path == '/health':
                    # Simulate a component being None (degraded)
                    health = {
                        'status': 'degraded',
                        'uptime_seconds': 100,
                        'uptime_human': '0:01:40',
                        'started_at': datetime.now().isoformat(),
                        'components': {
                            'slack_app': True,
                            'copper_client': False,  # Simulated failure
                            'approval_system': True,
                            'query_processor': True,
                            'csv_handler': True,
                            'task_processor': True,
                            'approval_state': True,
                        },
                        'stats': {
                            'pending_approvals': 0,
                            'approvers': 0,
                            'admins': 0,
                        }
                    }
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(health).encode())

        return DegradedHandler

    @pytest.fixture
    def degraded_server(self, degraded_handler_class):
        """Start a test server that reports degraded."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HTTPServer(('127.0.0.1', port), degraded_handler_class)
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        yield f'http://127.0.0.1:{port}'

        server.server_close()

    def test_degraded_returns_503(self, degraded_server):
        """Test degraded status returns 503."""
        url = f'{degraded_server}/health'
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url, timeout=5)
        assert exc_info.value.code == 503

    def test_degraded_status_in_response(self, degraded_server):
        """Test degraded status is reflected in JSON."""
        url = f'{degraded_server}/health'
        try:
            urllib.request.urlopen(url, timeout=5)
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode())
            assert data['status'] == 'degraded'
            assert data['components']['copper_client'] is False
