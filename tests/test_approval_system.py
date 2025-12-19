"""Tests for approval system."""

import pytest
import os
import json
from approval_system import ApprovalSystem


@pytest.fixture
def approval_system(tmp_path):
    """Create an ApprovalSystem instance for testing with isolated storage."""
    return ApprovalSystem(data_dir=str(tmp_path))


class TestApprovalSystemApprovers:
    """Test approver management."""

    def test_add_approver(self, approval_system):
        """Test adding an approver."""
        approval_system.add_approver("user123")
        assert approval_system.is_approver("user123")

    def test_remove_approver(self, approval_system):
        """Test removing an approver."""
        approval_system.add_approver("user123")
        approval_system.remove_approver("user123")
        assert not approval_system.is_approver("user123")

    def test_get_approvers(self, approval_system):
        """Test getting list of approvers."""
        approval_system.add_approver("user1")
        approval_system.add_approver("user2")
        approvers = approval_system.get_approvers()
        assert len(approvers) == 2
        assert "user1" in approvers
        assert "user2" in approvers


class TestApprovalSystemRequests:
    """Test request creation and management."""

    def test_create_update_request(self, approval_system):
        """Test creating an update request."""
        request_id = approval_system.create_update_request(
            requester_id="user123",
            entity_type="person",
            entity_id=456,
            updates={"email": "new@example.com"},
            entity_name="John Doe"
        )

        assert request_id is not None
        request = approval_system.get_request(request_id)
        assert request is not None
        assert request["entity_type"] == "person"
        assert request["entity_id"] == 456
        assert request["status"] == "pending"

    def test_create_create_request(self, approval_system):
        """Test creating a create request."""
        request_id = approval_system.create_request(
            requester_id="user123",
            operation="create",
            entity_type="company",
            data={"name": "New Company"},
            entity_name="New Company"
        )

        assert request_id is not None
        request = approval_system.get_request(request_id)
        assert request["operation"] == "create"
        assert request["entity_type"] == "company"

    def test_create_delete_request(self, approval_system):
        """Test creating a delete request."""
        request_id = approval_system.create_request(
            requester_id="user123",
            operation="delete",
            entity_type="opportunity",
            entity_id=789,
            entity_name="Old Deal"
        )

        assert request_id is not None
        request = approval_system.get_request(request_id)
        assert request["operation"] == "delete"
        assert request["entity_id"] == 789

    def test_get_pending_requests(self, approval_system):
        """Test getting pending requests."""
        approval_system.create_request(
            requester_id="user1",
            operation="create",
            entity_type="person",
            data={"name": "Test"},
            entity_name="Test"
        )
        approval_system.create_request(
            requester_id="user2",
            operation="update",
            entity_type="company",
            entity_id=123,
            data={"city": "NYC"},
            entity_name="Company"
        )

        pending = approval_system.get_pending_requests()
        assert len(pending) == 2


class TestApprovalSystemApproval:
    """Test approval/rejection workflow."""

    def test_approve_request(self, approval_system):
        """Test approving a request."""
        approval_system.add_approver("approver1")

        request_id = approval_system.create_update_request(
            requester_id="user123",
            entity_type="person",
            entity_id=456,
            updates={"email": "new@example.com"},
            entity_name="John Doe"
        )

        result = approval_system.approve_request(request_id, "approver1")
        assert result is True

        request = approval_system.get_request(request_id)
        assert request["status"] == "approved"
        assert request["approved_by"] == "approver1"

    def test_reject_request(self, approval_system):
        """Test rejecting a request."""
        approval_system.add_approver("approver1")

        request_id = approval_system.create_update_request(
            requester_id="user123",
            entity_type="person",
            entity_id=456,
            updates={"email": "new@example.com"},
            entity_name="John Doe"
        )

        result = approval_system.reject_request(request_id, "approver1", "Not needed")
        assert result is True

        # Request should be removed after rejection
        request = approval_system.get_request(request_id)
        assert request is None

    def test_unauthorized_approval(self, approval_system):
        """Test that non-approvers cannot approve."""
        request_id = approval_system.create_update_request(
            requester_id="user123",
            entity_type="person",
            entity_id=456,
            updates={"email": "new@example.com"},
            entity_name="John Doe"
        )

        result = approval_system.approve_request(request_id, "random_user")
        assert result is False

    def test_complete_request(self, approval_system):
        """Test completing a request."""
        approval_system.add_approver("approver1")

        request_id = approval_system.create_update_request(
            requester_id="user123",
            entity_type="person",
            entity_id=456,
            updates={"email": "new@example.com"},
            entity_name="John Doe"
        )

        approval_system.approve_request(request_id, "approver1")
        approval_system.complete_request(request_id)

        request = approval_system.get_request(request_id)
        assert request is None  # Removed after completion


class TestApprovalSystemPersistence:
    """Test persistence across restarts."""

    def test_approvers_persist(self, tmp_path):
        """Test that approvers survive a restart."""
        # Create first instance and add approvers
        system1 = ApprovalSystem(data_dir=str(tmp_path))
        system1.add_approver("user1")
        system1.add_approver("user2")

        # Create second instance (simulating restart)
        system2 = ApprovalSystem(data_dir=str(tmp_path))

        # Approvers should be loaded
        assert system2.is_approver("user1")
        assert system2.is_approver("user2")
        assert len(system2.get_approvers()) == 2

    def test_pending_requests_persist(self, tmp_path):
        """Test that pending requests survive a restart."""
        # Create first instance and add a request
        system1 = ApprovalSystem(data_dir=str(tmp_path))
        request_id = system1.create_request(
            requester_id="user123",
            operation="update",
            entity_type="person",
            entity_id=456,
            data={"email": "new@example.com"},
            entity_name="John Doe"
        )

        # Create second instance (simulating restart)
        system2 = ApprovalSystem(data_dir=str(tmp_path))

        # Request should be loaded
        request = system2.get_request(request_id)
        assert request is not None
        assert request["entity_type"] == "person"
        assert request["status"] == "pending"

    def test_state_file_created(self, tmp_path):
        """Test that state file is created."""
        system = ApprovalSystem(data_dir=str(tmp_path))
        system.add_approver("user1")

        state_file = os.path.join(str(tmp_path), "approval_state.json")
        assert os.path.exists(state_file)

        # Verify file contents
        with open(state_file, 'r') as f:
            state = json.load(f)
        assert "user1" in state["approvers"]

    def test_corrupted_state_file_handled(self, tmp_path):
        """Test that corrupted state file doesn't crash the system."""
        # Write corrupted JSON
        state_file = os.path.join(str(tmp_path), "approval_state.json")
        with open(state_file, 'w') as f:
            f.write("{invalid json")

        # Should start fresh without crashing
        system = ApprovalSystem(data_dir=str(tmp_path))
        assert len(system.get_approvers()) == 0
        assert len(system.get_pending_requests()) == 0

    def test_history_persists(self, tmp_path):
        """Test that approval history survives restart."""
        system1 = ApprovalSystem(data_dir=str(tmp_path))
        system1.add_approver("approver1")

        request_id = system1.create_request(
            requester_id="user123",
            operation="create",
            entity_type="company",
            data={"name": "Test Co"},
            entity_name="Test Co"
        )
        system1.approve_request(request_id, "approver1")
        system1.complete_request(request_id)

        # Restart
        system2 = ApprovalSystem(data_dir=str(tmp_path))

        # History should be preserved
        assert len(system2.approval_history) == 2  # approved + completed entries
