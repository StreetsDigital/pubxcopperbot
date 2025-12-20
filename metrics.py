"""Prometheus metrics for Copper CRM Slack Bot."""

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

logger = logging.getLogger(__name__)

# Type variable for generic function decorator
F = TypeVar('F', bound=Callable[..., Any])

# =============================================================================
# APPLICATION INFO
# =============================================================================

APP_INFO = Info(
    'copperbot',
    'Information about the Copper CRM Slack Bot'
)
APP_INFO.info({
    'version': '1.0.0',
    'component': 'slack_bot',
})

# =============================================================================
# REQUEST COUNTERS
# =============================================================================

SLACK_COMMANDS_TOTAL = Counter(
    'copperbot_slack_commands_total',
    'Total number of Slack slash commands received',
    ['command']
)

SLACK_EVENTS_TOTAL = Counter(
    'copperbot_slack_events_total',
    'Total number of Slack events processed',
    ['event_type']
)

COPPER_API_REQUESTS_TOTAL = Counter(
    'copperbot_copper_api_requests_total',
    'Total number of Copper API requests',
    ['operation', 'entity_type', 'status']
)

APPROVAL_REQUESTS_TOTAL = Counter(
    'copperbot_approval_requests_total',
    'Total number of approval requests',
    ['operation', 'entity_type', 'status']
)

# =============================================================================
# ERROR COUNTERS
# =============================================================================

ERRORS_TOTAL = Counter(
    'copperbot_errors_total',
    'Total number of errors',
    ['component', 'error_type']
)

VALIDATION_ERRORS_TOTAL = Counter(
    'copperbot_validation_errors_total',
    'Total number of input validation errors',
    ['entity_type']
)

# =============================================================================
# OPERATION TIMING
# =============================================================================

COPPER_API_DURATION_SECONDS = Histogram(
    'copperbot_copper_api_duration_seconds',
    'Time spent on Copper API operations',
    ['operation', 'entity_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

SLACK_COMMAND_DURATION_SECONDS = Histogram(
    'copperbot_slack_command_duration_seconds',
    'Time spent processing Slack commands',
    ['command'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# =============================================================================
# GAUGES
# =============================================================================

PENDING_APPROVALS = Gauge(
    'copperbot_pending_approvals',
    'Current number of pending approval requests'
)

ACTIVE_APPROVERS = Gauge(
    'copperbot_active_approvers',
    'Current number of configured approvers'
)

UPTIME_SECONDS = Gauge(
    'copperbot_uptime_seconds',
    'Bot uptime in seconds'
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def track_slack_command(command: str) -> Callable[[F], F]:
    """
    Decorator to track Slack command metrics.

    Args:
        command: Command name (e.g., '/copper', '/copper-create')

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            SLACK_COMMANDS_TOTAL.labels(command=command).inc()
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                ERRORS_TOTAL.labels(
                    component='slack_command',
                    error_type=type(e).__name__
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                SLACK_COMMAND_DURATION_SECONDS.labels(
                    command=command
                ).observe(duration)
        return wrapper  # type: ignore
    return decorator


def track_copper_operation(
    operation: str,
    entity_type: str,
    success: bool,
    duration: float
) -> None:
    """
    Record metrics for a Copper API operation.

    Args:
        operation: Operation type (create, read, update, delete)
        entity_type: Entity type (people, companies, etc.)
        success: Whether the operation succeeded
        duration: Operation duration in seconds
    """
    status = 'success' if success else 'error'
    COPPER_API_REQUESTS_TOTAL.labels(
        operation=operation,
        entity_type=entity_type,
        status=status
    ).inc()
    COPPER_API_DURATION_SECONDS.labels(
        operation=operation,
        entity_type=entity_type
    ).observe(duration)


def track_approval_request(
    operation: str,
    entity_type: str,
    status: str
) -> None:
    """
    Record metrics for an approval request.

    Args:
        operation: Operation type (create, update, delete)
        entity_type: Entity type
        status: Request status (created, approved, rejected)
    """
    APPROVAL_REQUESTS_TOTAL.labels(
        operation=operation,
        entity_type=entity_type,
        status=status
    ).inc()


def track_validation_error(entity_type: str) -> None:
    """
    Record a validation error.

    Args:
        entity_type: Entity type that failed validation
    """
    VALIDATION_ERRORS_TOTAL.labels(entity_type=entity_type).inc()


def update_approval_gauges(pending_count: int, approver_count: int) -> None:
    """
    Update gauge values for approvals.

    Args:
        pending_count: Number of pending approvals
        approver_count: Number of configured approvers
    """
    PENDING_APPROVALS.set(pending_count)
    ACTIVE_APPROVERS.set(approver_count)


def update_uptime(start_time: float) -> None:
    """
    Update the uptime gauge.

    Args:
        start_time: Unix timestamp when bot started
    """
    UPTIME_SECONDS.set(time.time() - start_time)


def get_metrics() -> bytes:
    """
    Get current metrics in Prometheus format.

    Returns:
        Prometheus metrics as bytes
    """
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """
    Get the content type for Prometheus metrics.

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST
