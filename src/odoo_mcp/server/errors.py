from __future__ import annotations

import http.client
import socket
import xmlrpc.client
from http import HTTPStatus
from typing import Any


class OdooError(Exception):
    """Structured Odoo-facing error with stable classification metadata."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "odoo_error",
        status_code: int = HTTPStatus.BAD_GATEWAY,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = int(status_code)
        self.retryable = retryable
        self.details = details or {}


class OdooConfigurationError(OdooError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            category="configuration_error",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            retryable=False,
            details=details,
        )


class OdooAuthenticationError(OdooError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            category="authentication_error",
            status_code=HTTPStatus.UNAUTHORIZED,
            retryable=False,
            details=details,
        )


class OdooAuthorizationError(OdooError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            category="authorization_error",
            status_code=HTTPStatus.FORBIDDEN,
            retryable=False,
            details=details,
        )


class OdooTimeoutError(OdooError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            category="timeout",
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            retryable=True,
            details=details,
        )


class OdooConnectionError(OdooError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            category="connection_error",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            retryable=True,
            details=details,
        )


class OdooProtocolError(OdooError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = HTTPStatus.BAD_GATEWAY,
        retryable: bool = False,
        category: str = "protocol_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            category=category,
            status_code=status_code,
            retryable=retryable,
            details=details,
        )


class OdooRemoteError(OdooError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        category: str = "remote_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            category=category,
            status_code=HTTPStatus.BAD_GATEWAY,
            retryable=retryable,
            details=details,
        )


class OdooRateLimitError(OdooError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            category="rate_limit",
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            retryable=True,
            details=details,
        )


RETRYABLE_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def normalize_odoo_error(exc: Exception, *, operation: str | None = None) -> OdooError:
    """Map transport and XML-RPC failures into a stable error taxonomy."""
    if isinstance(exc, OdooError):
        return exc

    operation_display = operation or "Odoo request"

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return OdooTimeoutError(
            f"{operation_display} timed out.",
            details={"exception_type": type(exc).__name__},
        )

    if isinstance(exc, http.client.RemoteDisconnected):
        return OdooConnectionError(
            f"{operation_display} failed because the Odoo server closed the connection.",
            details={"exception_type": type(exc).__name__},
        )

    if isinstance(
        exc,
        (
            ConnectionRefusedError,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
        ),
    ):
        return OdooConnectionError(
            f"{operation_display} failed because the network connection was interrupted.",
            details={"exception_type": type(exc).__name__},
        )

    if isinstance(exc, socket.gaierror):
        return OdooConnectionError(
            f"{operation_display} failed because the Odoo hostname could not be resolved.",
            details={"exception_type": type(exc).__name__, "errno": exc.errno},
        )

    if isinstance(exc, xmlrpc.client.ProtocolError):
        code = int(exc.errcode)
        details = {
            "url": exc.url,
            "http_status": code,
            "http_message": exc.errmsg,
        }
        if code == HTTPStatus.UNAUTHORIZED:
            return OdooAuthenticationError(
                "Odoo XML-RPC endpoint rejected the supplied credentials.",
                details=details,
            )
        if code == HTTPStatus.FORBIDDEN:
            return OdooAuthorizationError(
                "Authenticated Odoo user is not allowed to access this XML-RPC endpoint.",
                details=details,
            )
        retryable = code in RETRYABLE_HTTP_STATUS_CODES
        category = "upstream_rate_limit" if code == HTTPStatus.TOO_MANY_REQUESTS else "protocol_error"
        return OdooProtocolError(
            f"Odoo XML-RPC endpoint returned HTTP {code}: {exc.errmsg}",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE if retryable else HTTPStatus.BAD_GATEWAY,
            retryable=retryable,
            category=category,
            details=details,
        )

    if isinstance(exc, xmlrpc.client.Fault):
        fault_text = str(exc.faultString or exc)
        normalized_fault = fault_text.lower()
        details = {
            "fault_code": exc.faultCode,
            "fault_string": fault_text,
        }
        if "not allowed to access" in normalized_fault or "access denied" in normalized_fault:
            return OdooAuthorizationError(
                "Authenticated Odoo user is not allowed to perform this operation.",
                details=details,
            )
        if "authentication" in normalized_fault or "invalid login" in normalized_fault:
            return OdooAuthenticationError(
                "Odoo rejected the supplied credentials.",
                details=details,
            )
        return OdooRemoteError(
            f"Odoo rejected the operation: {fault_text}",
            category="application_error",
            retryable=False,
            details=details,
        )

    if isinstance(exc, socket.error):
        return OdooConnectionError(
            f"{operation_display} failed because the network connection to Odoo could not be established.",
            details={"exception_type": type(exc).__name__},
        )

    return OdooRemoteError(
        f"{operation_display} failed: {exc}",
        retryable=False,
        details={"exception_type": type(exc).__name__},
    )


def error_to_payload(
    exc: Exception,
    *,
    model: str | None = None,
    method: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_odoo_error(exc, operation=operation)
    payload: dict[str, Any] = {
        "success": False,
        "error": normalized.message,
        "error_category": normalized.category,
        "retryable": normalized.retryable,
    }
    if model is not None:
        payload["model"] = model
    if method is not None:
        payload["method"] = method
    if normalized.details:
        payload["error_details"] = normalized.details
    return payload
