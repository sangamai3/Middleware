from enum import StrEnum


class RetryBehavior(StrEnum):
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    DEPLOY_TIME = "deploy_time"
    ROW_LEVEL = "row_level"


class SangamMWException(Exception):
    retry_behavior: RetryBehavior = RetryBehavior.NON_RETRYABLE

    def __init__(
        self,
        message: str,
        *,
        flow_id: str = "",
        run_id: str = "",
        step_id: str = "",
    ) -> None:
        super().__init__(message)
        self.flow_id = flow_id
        self.run_id = run_id
        self.step_id = step_id


# ---------------------------------------------------------------------------
# Connector exceptions
# ---------------------------------------------------------------------------


class ConnectorException(SangamMWException):
    pass


class RateLimitError(ConnectorException):
    retry_behavior = RetryBehavior.RETRYABLE

    def __init__(self, message: str, retry_after: int | None = None, **kwargs: object) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class NetworkError(ConnectorException):
    retry_behavior = RetryBehavior.RETRYABLE


class AuthenticationError(ConnectorException):
    retry_behavior = RetryBehavior.NON_RETRYABLE


class ConnectorValidationError(ConnectorException):
    retry_behavior = RetryBehavior.DEPLOY_TIME


class DataReadError(ConnectorException):
    retry_behavior = RetryBehavior.NON_RETRYABLE


# ---------------------------------------------------------------------------
# Transform exceptions
# ---------------------------------------------------------------------------


class TransformException(SangamMWException):
    pass


class TransformSyntaxError(TransformException):
    retry_behavior = RetryBehavior.DEPLOY_TIME


class DataTypeError(TransformException):
    retry_behavior = RetryBehavior.ROW_LEVEL


class TransformMemoryError(TransformException):
    # Auto-promoted to PySpark by EngineRouter — not surfaced as user error.
    retry_behavior = RetryBehavior.RETRYABLE


# ---------------------------------------------------------------------------
# Flow exceptions
# ---------------------------------------------------------------------------


class FlowException(SangamMWException):
    pass


class FlowValidationError(FlowException):
    retry_behavior = RetryBehavior.DEPLOY_TIME


class FlowTimeoutError(FlowException):
    retry_behavior = RetryBehavior.NON_RETRYABLE


class FlowAbortedError(FlowException):
    retry_behavior = RetryBehavior.NON_RETRYABLE
