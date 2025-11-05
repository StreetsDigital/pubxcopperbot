"""Approval system for Copper CRM updates."""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


class ApprovalSystem:
    """Manage approval workflow for CRM updates."""

    def __init__(self):
        """Initialize the approval system."""
        # In-memory storage for pending approvals
        # In production, use a database
        self.pending_approvals = {}
        self.approval_history = []
        self.approvers = set()  # Set of Slack user IDs who can approve

    def add_approver(self, user_id: str):
        """
        Add a user as an approver.

        Args:
            user_id: Slack user ID
        """
        self.approvers.add(user_id)
        logger.info(f"Added approver: {user_id}")

    def remove_approver(self, user_id: str):
        """
        Remove a user from approvers.

        Args:
            user_id: Slack user ID
        """
        self.approvers.discard(user_id)
        logger.info(f"Removed approver: {user_id}")

    def is_approver(self, user_id: str) -> bool:
        """
        Check if a user is an approver.

        Args:
            user_id: Slack user ID

        Returns:
            True if user is an approver
        """
        return user_id in self.approvers

    def get_approvers(self) -> List[str]:
        """
        Get list of all approvers.

        Returns:
            List of Slack user IDs
        """
        return list(self.approvers)

    def create_update_request(
        self,
        requester_id: str,
        entity_type: str,
        entity_id: int,
        updates: Dict[str, Any],
        entity_name: str = "Unknown"
    ) -> str:
        """
        Create a new update request.

        Args:
            requester_id: Slack user ID of requester
            entity_type: Type of entity (person, company, opportunity)
            entity_id: Copper entity ID
            updates: Dictionary of fields to update
            entity_name: Name of the entity being updated

        Returns:
            Request ID
        """
        request_id = f"{entity_type}_{entity_id}_{datetime.now().timestamp()}"

        request = {
            'request_id': request_id,
            'requester_id': requester_id,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'entity_name': entity_name,
            'updates': updates,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'approved_by': None,
            'approved_at': None
        }

        self.pending_approvals[request_id] = request
        logger.info(f"Created update request: {request_id}")

        return request_id

    def get_pending_requests(self) -> List[Dict]:
        """
        Get all pending approval requests.

        Returns:
            List of pending requests
        """
        return [
            req for req in self.pending_approvals.values()
            if req['status'] == 'pending'
        ]

    def get_request(self, request_id: str) -> Optional[Dict]:
        """
        Get a specific request.

        Args:
            request_id: Request ID

        Returns:
            Request data or None
        """
        return self.pending_approvals.get(request_id)

    def approve_request(self, request_id: str, approver_id: str) -> bool:
        """
        Approve an update request.

        Args:
            request_id: Request ID
            approver_id: Slack user ID of approver

        Returns:
            True if successful
        """
        if request_id not in self.pending_approvals:
            logger.error(f"Request not found: {request_id}")
            return False

        if not self.is_approver(approver_id):
            logger.error(f"User {approver_id} is not an approver")
            return False

        request = self.pending_approvals[request_id]

        if request['status'] != 'pending':
            logger.error(f"Request {request_id} is not pending")
            return False

        request['status'] = 'approved'
        request['approved_by'] = approver_id
        request['approved_at'] = datetime.now().isoformat()

        self.approval_history.append(dict(request))

        logger.info(f"Request {request_id} approved by {approver_id}")
        return True

    def reject_request(self, request_id: str, approver_id: str, reason: str = "") -> bool:
        """
        Reject an update request.

        Args:
            request_id: Request ID
            approver_id: Slack user ID of approver
            reason: Rejection reason

        Returns:
            True if successful
        """
        if request_id not in self.pending_approvals:
            logger.error(f"Request not found: {request_id}")
            return False

        if not self.is_approver(approver_id):
            logger.error(f"User {approver_id} is not an approver")
            return False

        request = self.pending_approvals[request_id]

        if request['status'] != 'pending':
            logger.error(f"Request {request_id} is not pending")
            return False

        request['status'] = 'rejected'
        request['approved_by'] = approver_id
        request['approved_at'] = datetime.now().isoformat()
        request['rejection_reason'] = reason

        self.approval_history.append(dict(request))

        # Remove from pending
        del self.pending_approvals[request_id]

        logger.info(f"Request {request_id} rejected by {approver_id}")
        return True

    def complete_request(self, request_id: str):
        """
        Mark a request as completed after successful update.

        Args:
            request_id: Request ID
        """
        if request_id in self.pending_approvals:
            request = self.pending_approvals[request_id]
            request['status'] = 'completed'
            request['completed_at'] = datetime.now().isoformat()

            self.approval_history.append(dict(request))
            del self.pending_approvals[request_id]

            logger.info(f"Request {request_id} completed")

    def format_request_for_approval(self, request: Dict) -> str:
        """
        Format a request for display in Slack.

        Args:
            request: Request data

        Returns:
            Formatted string
        """
        entity_type = request['entity_type'].title()
        entity_name = request['entity_name']
        requester = request['requester_id']
        updates = request['updates']

        message = f"*Update Request: {entity_type}*\n\n"
        message += f"📝 Entity: {entity_name}\n"
        message += f"👤 Requested by: <@{requester}>\n"
        message += f"🕐 Time: {request['created_at']}\n\n"
        message += "*Proposed Changes:*\n"

        for field, value in updates.items():
            message += f"• {field}: `{value}`\n"

        return message

    def create_approval_blocks(self, request_id: str, request: Dict) -> List[Dict]:
        """
        Create Slack Block Kit blocks for approval UI.

        Args:
            request_id: Request ID
            request: Request data

        Returns:
            List of Block Kit blocks
        """
        entity_type = request['entity_type'].title()
        entity_name = request['entity_name']
        requester = request['requester_id']
        updates = request['updates']

        # Format updates as fields
        update_fields = []
        for field, value in updates.items():
            update_fields.append({
                "type": "mrkdwn",
                "text": f"*{field}:*\n{value}"
            })

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔔 Update Request: {entity_type}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Entity:*\n{entity_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Requested by:*\n<@{requester}>"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Proposed Changes:*"
                }
            }
        ]

        # Add update fields in chunks of 10 (Slack limit)
        for i in range(0, len(update_fields), 10):
            chunk = update_fields[i:i+10]
            blocks.append({
                "type": "section",
                "fields": chunk
            })

        # Add action buttons
        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve"
                        },
                        "style": "primary",
                        "value": request_id,
                        "action_id": f"approve_{request_id}"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "❌ Reject"
                        },
                        "style": "danger",
                        "value": request_id,
                        "action_id": f"reject_{request_id}"
                    }
                ]
            }
        ])

        return blocks
