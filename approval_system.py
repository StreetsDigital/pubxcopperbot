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

    def create_request(
        self,
        requester_id: str,
        operation: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        entity_name: str = "Unknown"
    ) -> str:
        """
        Create a new operation request (create, update, or delete).

        Args:
            requester_id: Slack user ID of requester
            operation: Type of operation ('create', 'update', 'delete')
            entity_type: Type of entity (person, company, opportunity, etc.)
            entity_id: Copper entity ID (for update/delete)
            data: Dictionary with data (updates for update, new data for create)
            entity_name: Name of the entity

        Returns:
            Request ID
        """
        timestamp = datetime.now().timestamp()
        if entity_id:
            request_id = f"{operation}_{entity_type}_{entity_id}_{timestamp}"
        else:
            request_id = f"{operation}_{entity_type}_{timestamp}"

        request = {
            'request_id': request_id,
            'requester_id': requester_id,
            'operation': operation,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'entity_name': entity_name,
            'data': data or {},
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'approved_by': None,
            'approved_at': None
        }

        self.pending_approvals[request_id] = request
        logger.info(f"Created {operation} request: {request_id}")

        return request_id

    def create_update_request(
        self,
        requester_id: str,
        entity_type: str,
        entity_id: int,
        updates: Dict[str, Any],
        entity_name: str = "Unknown"
    ) -> str:
        """
        Create a new update request (backward compatibility).

        Args:
            requester_id: Slack user ID of requester
            entity_type: Type of entity (person, company, opportunity)
            entity_id: Copper entity ID
            updates: Dictionary of fields to update
            entity_name: Name of the entity being updated

        Returns:
            Request ID
        """
        return self.create_request(
            requester_id=requester_id,
            operation='update',
            entity_type=entity_type,
            entity_id=entity_id,
            data=updates,
            entity_name=entity_name
        )

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
        operation = request.get('operation', 'update')
        entity_type = request['entity_type'].title()
        entity_name = request['entity_name']
        requester = request['requester_id']
        data = request.get('data', request.get('updates', {}))

        if operation == 'create':
            message = f"*Create Request: New {entity_type}*\n\n"
            message += f"👤 Requested by: <@{requester}>\n"
            message += f"🕐 Time: {request['created_at']}\n\n"
            message += "*New Record Details:*\n"
        elif operation == 'delete':
            message = f"*Delete Request: {entity_type}*\n\n"
            message += f"📝 Entity: {entity_name}\n"
            message += f"🆔 ID: {request.get('entity_id', 'N/A')}\n"
            message += f"👤 Requested by: <@{requester}>\n"
            message += f"🕐 Time: {request['created_at']}\n\n"
            message += "⚠️ *This will permanently delete the record!*\n"
            return message
        else:  # update
            message = f"*Update Request: {entity_type}*\n\n"
            message += f"📝 Entity: {entity_name}\n"
            message += f"👤 Requested by: <@{requester}>\n"
            message += f"🕐 Time: {request['created_at']}\n\n"
            message += "*Proposed Changes:*\n"

        for field, value in data.items():
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
        operation = request.get('operation', 'update')
        entity_type = request['entity_type'].title()
        entity_name = request['entity_name']
        requester = request['requester_id']
        data = request.get('data', request.get('updates', {}))

        # Header based on operation
        if operation == 'create':
            header_text = f"➕ Create Request: New {entity_type}"
        elif operation == 'delete':
            header_text = f"🗑️ Delete Request: {entity_type}"
        else:
            header_text = f"✏️ Update Request: {entity_type}"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text
                }
            }
        ]

        # Section fields based on operation
        if operation == 'delete':
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Entity:*\n{entity_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*ID:*\n{request.get('entity_id', 'N/A')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Requested by:*\n<@{requester}>"
                    }
                ]
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "⚠️ *Warning: This will permanently delete the record!*"
                }
            })
        else:
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Entity:*\n{entity_name}" if operation != 'create' else f"*Type:*\n{entity_type}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Requested by:*\n<@{requester}>"
                    }
                ]
            })

        blocks.append({"type": "divider"})

        # Data fields
        if data:
            data_fields = []
            for field, value in data.items():
                data_fields.append({
                    "type": "mrkdwn",
                    "text": f"*{field}:*\n{value}"
                })

            label = "New Record Details:" if operation == 'create' else "Proposed Changes:"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{label}*"
                }
            })

            # Add data fields in chunks of 10 (Slack limit)
            for i in range(0, len(data_fields), 10):
                chunk = data_fields[i:i+10]
                blocks.append({
                    "type": "section",
                    "fields": chunk
                })

        # Action buttons
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
