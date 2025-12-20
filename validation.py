"""Input validation and sanitization for Copper CRM operations."""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Type aliases
JsonDict = Dict[str, Any]
ValidationResult = Tuple[bool, JsonDict, List[str]]


# =============================================================================
# FIELD ALLOWLISTS
# Define allowed fields for each entity type to prevent injection attacks
# =============================================================================

ALLOWED_FIELDS: Dict[str, Set[str]] = {
    'people': {
        'name', 'prefix', 'first_name', 'middle_name', 'last_name', 'suffix',
        'emails', 'phone_numbers', 'address', 'assignee_id', 'company_id',
        'company_name', 'contact_type_id', 'details', 'socials', 'tags',
        'title', 'websites', 'custom_fields',
    },
    'companies': {
        'name', 'assignee_id', 'contact_type_id', 'details', 'email_domain',
        'phone_numbers', 'socials', 'tags', 'websites', 'address',
        'custom_fields',
    },
    'opportunities': {
        'name', 'assignee_id', 'close_date', 'company_id', 'company_name',
        'customer_source_id', 'details', 'loss_reason_id', 'monetary_unit',
        'monetary_value', 'pipeline_id', 'pipeline_stage_id',
        'primary_contact_id', 'priority', 'status', 'tags', 'win_probability',
        'custom_fields',
    },
    'leads': {
        'name', 'prefix', 'first_name', 'middle_name', 'last_name', 'suffix',
        'assignee_id', 'company_name', 'customer_source_id', 'details',
        'email', 'monetary_unit', 'monetary_value', 'phone_numbers',
        'socials', 'status', 'status_id', 'tags', 'title', 'websites',
        'address', 'custom_fields',
    },
    'tasks': {
        'name', 'assignee_id', 'details', 'due_date', 'reminder_date',
        'priority', 'status', 'tags', 'related_resource', 'custom_fields',
    },
    'projects': {
        'name', 'assignee_id', 'details', 'status', 'tags', 'related_resource',
        'custom_fields',
    },
}

# Fields that are required for creation
REQUIRED_FIELDS: Dict[str, Set[str]] = {
    'people': {'name'},
    'companies': {'name'},
    'opportunities': {'name'},
    'leads': {'name'},
    'tasks': {'name'},
    'projects': {'name'},
}

# Maximum lengths for string fields
MAX_LENGTHS: Dict[str, int] = {
    'name': 500,
    'title': 200,
    'details': 10000,
    'company_name': 500,
    'email_domain': 255,
}

# Pattern for valid email addresses
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_and_sanitize(
    entity_type: str,
    data: JsonDict,
    operation: str = 'create'
) -> ValidationResult:
    """
    Validate and sanitize input data for Copper CRM operations.

    Args:
        entity_type: Type of entity (people, companies, etc.)
        data: Input data to validate
        operation: 'create' or 'update'

    Returns:
        Tuple of (is_valid, sanitized_data, error_messages)
    """
    errors: List[str] = []
    sanitized: JsonDict = {}

    # Normalize entity type
    entity_key = _normalize_entity_type(entity_type)

    if entity_key not in ALLOWED_FIELDS:
        errors.append(f"Unknown entity type: {entity_type}")
        return False, {}, errors

    allowed = ALLOWED_FIELDS[entity_key]
    required = REQUIRED_FIELDS.get(entity_key, set())

    # Filter and sanitize fields
    for field, value in data.items():
        if field not in allowed:
            logger.warning(
                f"Blocked disallowed field '{field}' for {entity_key}"
            )
            errors.append(f"Field '{field}' is not allowed for {entity_key}")
            continue

        # Sanitize the value
        sanitized_value = _sanitize_value(field, value)
        if sanitized_value is not None:
            sanitized[field] = sanitized_value

    # Check required fields for create operations
    if operation == 'create':
        for field in required:
            if field not in sanitized or not sanitized[field]:
                errors.append(f"Required field '{field}' is missing or empty")

    # Validate specific field types
    field_errors = _validate_field_types(entity_key, sanitized)
    errors.extend(field_errors)

    is_valid = len(errors) == 0
    return is_valid, sanitized, errors


def _normalize_entity_type(entity_type: str) -> str:
    """Normalize entity type to plural form."""
    type_lower = entity_type.lower()

    # Map singular to plural
    mappings = {
        'person': 'people',
        'contact': 'people',
        'company': 'companies',
        'opportunity': 'opportunities',
        'deal': 'opportunities',
        'lead': 'leads',
        'task': 'tasks',
        'project': 'projects',
    }

    return mappings.get(type_lower, type_lower)


def _sanitize_value(field: str, value: Any) -> Any:
    """Sanitize a single field value."""
    if value is None:
        return None

    # String sanitization
    if isinstance(value, str):
        # Strip whitespace
        sanitized = value.strip()

        # Check max length
        max_len = MAX_LENGTHS.get(field, 1000)
        if len(sanitized) > max_len:
            sanitized = sanitized[:max_len]
            logger.warning(
                f"Truncated field '{field}' to {max_len} characters"
            )

        return sanitized if sanitized else None

    # List sanitization (emails, phone_numbers, tags, etc.)
    if isinstance(value, list):
        sanitized_list: List[Any] = []
        for item in value:
            if isinstance(item, dict):
                # Sanitize nested dict fields
                sanitized_item = {}
                for k, v in item.items():
                    if isinstance(v, str):
                        v = v.strip()
                    if v:
                        sanitized_item[k] = v
                if sanitized_item:
                    sanitized_list.append(sanitized_item)
            elif isinstance(item, str):
                item = item.strip()
                if item:
                    sanitized_list.append(item)
            else:
                sanitized_list.append(item)
        return sanitized_list if sanitized_list else None

    # Dict sanitization (address, related_resource, etc.)
    if isinstance(value, dict):
        sanitized_dict = {}
        for k, v in value.items():
            if isinstance(v, str):
                v = v.strip()
            if v is not None and v != '':
                sanitized_dict[k] = v
        return sanitized_dict if sanitized_dict else None

    # Numeric values pass through
    if isinstance(value, (int, float)):
        return value

    # Boolean values pass through
    if isinstance(value, bool):
        return value

    return value


def _validate_field_types(entity_type: str, data: JsonDict) -> List[str]:
    """Validate specific field types."""
    errors: List[str] = []

    # Validate emails if present
    if 'emails' in data and data['emails']:
        for email_obj in data['emails']:
            if isinstance(email_obj, dict):
                email = email_obj.get('email', '')
                if email and not EMAIL_PATTERN.match(email):
                    errors.append(f"Invalid email format: {email}")

    # Validate email (for leads)
    if 'email' in data and data['email']:
        if isinstance(data['email'], dict):
            email = data['email'].get('email', '')
            if email and not EMAIL_PATTERN.match(email):
                errors.append(f"Invalid email format: {email}")
        elif isinstance(data['email'], str):
            if not EMAIL_PATTERN.match(data['email']):
                errors.append(f"Invalid email format: {data['email']}")

    # Validate monetary values
    if 'monetary_value' in data and data['monetary_value'] is not None:
        try:
            value = float(data['monetary_value'])
            if value < 0:
                errors.append("Monetary value cannot be negative")
        except (ValueError, TypeError):
            errors.append("Monetary value must be a number")

    # Validate related_resource for tasks/projects
    if 'related_resource' in data and data['related_resource']:
        resource = data['related_resource']
        if isinstance(resource, dict):
            if 'type' not in resource:
                errors.append("related_resource must have a 'type' field")
            if 'id' not in resource:
                errors.append("related_resource must have an 'id' field")

    return errors


def validate_entity_id(entity_id: Any) -> Optional[int]:
    """
    Validate and convert entity ID to integer.

    Args:
        entity_id: ID to validate (can be string or int)

    Returns:
        Integer ID or None if invalid
    """
    if entity_id is None:
        return None

    try:
        id_int = int(entity_id)
        if id_int <= 0:
            return None
        return id_int
    except (ValueError, TypeError):
        return None
