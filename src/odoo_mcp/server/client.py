"""
Odoo XML-RPC client for MCP server integration.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
import socket
import ssl
import time
import urllib.parse
import xmlrpc.client
from dataclasses import dataclass
from typing import Any

from .errors import (
    OdooAuthenticationError,
    OdooConfigurationError,
    OdooError,
    RETRYABLE_HTTP_STATUS_CODES,
    normalize_odoo_error,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    timeout_seconds: int
    max_attempts: int
    backoff_seconds: float
    max_backoff_seconds: float
    max_redirects: int


class OdooClient:
    """Client for interacting with Odoo via XML-RPC."""

    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
        timeout: int = 10,
        verify_ssl: bool = True,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not re.match(r"^https?://", url):
            url = f"http://{url}"

        url = url.rstrip("/")

        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid: int | None = None
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.retry_policy = retry_policy or RetryPolicy(
            timeout_seconds=timeout,
            max_attempts=3,
            backoff_seconds=0.5,
            max_backoff_seconds=4.0,
            max_redirects=5,
        )
        self._common = None
        self._models = None

        parsed_url = urllib.parse.urlparse(self.url)
        self.hostname = parsed_url.netloc
        self._connect()

    def _connect(self) -> None:
        """Initialize XML-RPC endpoints and authenticate once."""
        is_https = self.url.startswith("https://")
        transport = RedirectTransport(
            use_https=is_https,
            verify_ssl=self.verify_ssl,
            retry_policy=self.retry_policy,
        )

        self._common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common",
            transport=transport,
            allow_none=True,
        )
        self._models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object",
            transport=transport,
            allow_none=True,
        )

        logger.info(
            "Connecting to Odoo url=%s db=%s user=%s timeout=%ss attempts=%s verify_ssl=%s",
            self.url,
            self.db,
            self.username,
            self.retry_policy.timeout_seconds,
            self.retry_policy.max_attempts,
            self.verify_ssl,
        )

        try:
            uid = self._common.authenticate(self.db, self.username, self.password, {})
        except Exception as exc:
            raise normalize_odoo_error(exc, operation="Odoo authentication") from exc

        if not uid:
            raise OdooAuthenticationError("Authentication failed: invalid username or password.")

        self.uid = int(uid)

    def _execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        """Execute an Odoo model method and classify transport faults."""
        if self.uid is None:
            raise OdooAuthenticationError("Odoo client is not authenticated.")

        try:
            return self._models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                method,
                list(args),
                kwargs,
            )
        except Exception as exc:
            raise normalize_odoo_error(exc, operation=f"Odoo call {model}.{method}") from exc

    def execute_method(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        return self._execute(model, method, *args, **kwargs)

    def get_models(self) -> dict[str, Any]:
        model_ids = self._execute("ir.model", "search", [])

        if not model_ids:
            return {
                "model_names": [],
                "models_details": {},
                "error": "No models found",
            }

        result = self._execute("ir.model", "read", model_ids, ["model", "name"])
        models = sorted(record["model"] for record in result)

        return {
            "model_names": models,
            "models_details": {
                record["model"]: {"name": record.get("name", "")}
                for record in result
            },
        }

    def get_model_info(self, model_name: str) -> dict[str, Any]:
        result = self.search_read(
            "ir.model",
            [("model", "=", model_name)],
            fields=["name", "model"],
            limit=1,
            raise_on_error=True,
        )

        if not result:
            return {"error": f"Model {model_name} not found"}

        return result[0]

    def get_model_fields(
        self,
        model_name: str,
        raise_on_error: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            kwargs: dict[str, Any] = {}
            if context is not None:
                kwargs["context"] = context
            return self._execute(model_name, "fields_get", **kwargs)
        except OdooError as exc:
            if raise_on_error:
                raise
            return {
                "error": exc.message,
                "error_category": exc.category,
                "retryable": exc.retryable,
            }

    def search_read(
        self,
        model_name: str,
        domain: list[Any],
        fields: list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        raise_on_error: bool = False,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            opts: dict[str, Any] = {}
            if offset:
                opts["offset"] = offset
            if fields is not None:
                opts["fields"] = fields
            if limit is not None:
                opts["limit"] = limit
            if order is not None:
                opts["order"] = order
            if context is not None:
                opts["context"] = context

            return self._execute(model_name, "search_read", domain, **opts)
        except OdooError:
            if raise_on_error:
                raise
            return []

    def read_records(
        self,
        model_name: str,
        ids: list[int],
        fields: list[str] | None = None,
        raise_on_error: bool = False,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            opts: dict[str, Any] = {}
            if fields is not None:
                opts["fields"] = fields
            if context is not None:
                opts["context"] = context
            return self._execute(model_name, "read", ids, **opts)
        except OdooError:
            if raise_on_error:
                raise
            return []


class RedirectTransport(xmlrpc.client.Transport):
    """Transport that adds timeout, retry backoff, SSL verification, and redirects."""

    RETRYABLE_NETWORK_ERRORS = (
        socket.timeout,
        TimeoutError,
        ConnectionResetError,
        ConnectionAbortedError,
        ConnectionRefusedError,
        BrokenPipeError,
        http.client.RemoteDisconnected,
        ssl.SSLError,
    )

    def __init__(
        self,
        *,
        use_https: bool = True,
        verify_ssl: bool = True,
        retry_policy: RetryPolicy | None = None,
        proxy: str | None = None,
    ) -> None:
        super().__init__()
        self.retry_policy = retry_policy or RetryPolicy(
            timeout_seconds=10,
            max_attempts=3,
            backoff_seconds=0.5,
            max_backoff_seconds=4.0,
            max_redirects=5,
        )
        self.timeout = self.retry_policy.timeout_seconds
        self.use_https = use_https
        self.verify_ssl = verify_ssl
        self.proxy = proxy or os.environ.get("HTTP_PROXY")
        self.context = None

        if use_https and not verify_ssl:
            self.context = ssl._create_unverified_context()

    def make_connection(self, host: str):
        if self.proxy:
            proxy_url = urllib.parse.urlparse(self.proxy)
            connection = http.client.HTTPConnection(
                proxy_url.hostname,
                proxy_url.port,
                timeout=self.timeout,
            )
            connection.set_tunnel(host)
            return connection

        if self.use_https and not self.verify_ssl:
            return http.client.HTTPSConnection(
                host,
                timeout=self.timeout,
                context=self.context,
            )
        if self.use_https:
            return http.client.HTTPSConnection(host, timeout=self.timeout)
        return http.client.HTTPConnection(host, timeout=self.timeout)

    def request(self, host, handler, request_body, verbose):
        current_host = host
        current_handler = handler
        redirects = 0
        attempt = 1

        while True:
            try:
                logger.debug(
                    "Odoo XML-RPC request host=%s handler=%s attempt=%s",
                    current_host,
                    current_handler,
                    attempt,
                )
                return super().request(current_host, current_handler, request_body, verbose)
            except xmlrpc.client.ProtocolError as exc:
                if (
                    exc.errcode in {301, 302, 303, 307, 308}
                    and exc.headers.get("location")
                    and redirects < self.retry_policy.max_redirects
                ):
                    redirects += 1
                    current_host, current_handler = self._follow_redirect(
                        current_host,
                        current_handler,
                        exc.headers["location"],
                    )
                    logger.info(
                        "Redirecting Odoo XML-RPC request to host=%s handler=%s (%s/%s)",
                        current_host,
                        current_handler,
                        redirects,
                        self.retry_policy.max_redirects,
                    )
                    continue

                if not self._should_retry_protocol(exc, attempt):
                    raise

                self._sleep_before_retry(attempt, reason=f"http {exc.errcode}")
                attempt += 1
            except self.RETRYABLE_NETWORK_ERRORS as exc:
                if attempt >= self.retry_policy.max_attempts:
                    raise

                if isinstance(exc, ssl.SSLError) and self.verify_ssl:
                    raise

                self._sleep_before_retry(attempt, reason=type(exc).__name__)
                attempt += 1
            except OSError as exc:
                if not self._should_retry_os_error(exc) or attempt >= self.retry_policy.max_attempts:
                    raise

                self._sleep_before_retry(attempt, reason=type(exc).__name__)
                attempt += 1

    def _follow_redirect(
        self,
        host: str,
        handler: str,
        location: str,
    ) -> tuple[str, str]:
        parsed = urllib.parse.urlparse(location)
        next_host = parsed.netloc or host
        next_handler = parsed.path or handler
        if parsed.query:
            next_handler = f"{next_handler}?{parsed.query}"
        return next_host, next_handler

    def _should_retry_protocol(self, exc: xmlrpc.client.ProtocolError, attempt: int) -> bool:
        return (
            exc.errcode in RETRYABLE_HTTP_STATUS_CODES
            and attempt < self.retry_policy.max_attempts
        )

    def _should_retry_os_error(self, exc: OSError) -> bool:
        retryable_errnos = {
            101,  # Network is unreachable
            103,  # Software caused connection abort
            104,  # Connection reset by peer
            110,  # Connection timed out
            111,  # Connection refused
        }
        return exc.errno in retryable_errnos if exc.errno is not None else False

    def _sleep_before_retry(self, attempt: int, *, reason: str) -> None:
        if attempt >= self.retry_policy.max_attempts:
            return

        backoff = min(
            self.retry_policy.backoff_seconds * (2 ** max(attempt - 1, 0)),
            self.retry_policy.max_backoff_seconds,
        )
        logger.warning(
            "Retrying Odoo XML-RPC request after %s because of %s (attempt %s/%s)",
            backoff,
            reason,
            attempt + 1,
            self.retry_policy.max_attempts,
        )
        if backoff > 0:
            time.sleep(backoff)


def load_config() -> dict[str, Any]:
    """
    Load Odoo configuration from environment variables or config file.

    Returns:
        dict: Configuration dictionary with at least `url` and `db`.
    """
    config_paths = [
        "./odoo_config.json",
        os.path.expanduser("~/.config/odoo/config.json"),
        os.path.expanduser("~/.odoo_config.json"),
    ]

    config: dict[str, Any] = {}

    for path in config_paths:
        expanded_path = os.path.expanduser(path)
        if os.path.exists(expanded_path):
            with open(expanded_path, "r", encoding="utf-8") as file_handle:
                config = json.load(file_handle)
            break

    env_mapping = {
        "ODOO_URL": "url",
        "ODOO_DB": "db",
        "ODOO_USERNAME": "username",
        "ODOO_PASSWORD": "password",
        "ODOO_TIMEOUT": "timeout",
        "ODOO_RETRY_ATTEMPTS": "retry_attempts",
        "ODOO_RETRY_BACKOFF_SECONDS": "retry_backoff_seconds",
        "ODOO_RETRY_BACKOFF_MAX_SECONDS": "retry_backoff_max_seconds",
        "ODOO_MAX_REDIRECTS": "max_redirects",
    }
    for env_name, config_key in env_mapping.items():
        value = os.environ.get(env_name)
        if value is not None:
            config[config_key] = value

    missing_keys = [key for key in ("url", "db") if not config.get(key)]
    if missing_keys:
        missing_display = ", ".join(missing_keys)
        raise OdooConfigurationError(
            "No Odoo configuration found. Please provide at least "
            f"{missing_display} in odoo_config.json or environment variables."
        )

    return config


def get_odoo_client(
    username: str | None = None,
    password: str | None = None,
    *,
    allow_config_fallback: bool = True,
) -> OdooClient:
    """Get a configured Odoo client instance."""
    config = load_config()

    timeout = max(int(os.environ.get("ODOO_TIMEOUT", str(config.get("timeout", 120)))), 1)
    verify_ssl_raw = os.environ.get(
        "ODOO_VERIFY_SSL",
        str(config.get("verify_ssl", 1)),
    )
    verify_ssl = str(verify_ssl_raw).lower() in {"1", "true", "yes", "on"}
    retry_attempts = max(
        int(os.environ.get("ODOO_RETRY_ATTEMPTS", str(config.get("retry_attempts", 3)))),
        1,
    )
    retry_backoff_seconds = max(
        float(
            os.environ.get(
                "ODOO_RETRY_BACKOFF_SECONDS",
                str(config.get("retry_backoff_seconds", 0.5)),
            )
        ),
        0.0,
    )
    retry_backoff_max_seconds = max(
        float(
            os.environ.get(
                "ODOO_RETRY_BACKOFF_MAX_SECONDS",
                str(config.get("retry_backoff_max_seconds", 4.0)),
            )
        ),
        retry_backoff_seconds,
    )
    max_redirects = max(
        int(os.environ.get("ODOO_MAX_REDIRECTS", str(config.get("max_redirects", 5)))),
        0,
    )

    resolved_username = username
    resolved_password = password

    if allow_config_fallback:
        if resolved_username is None:
            resolved_username = config.get("username")
        if resolved_password is None:
            resolved_password = config.get("password")

    if not resolved_username or not resolved_password:
        raise OdooConfigurationError(
            "Odoo username/password are required. For HTTP mode, send them via "
            "Basic Auth. For local fallback mode, add them to odoo_config.json "
            "or set ODOO_USERNAME and ODOO_PASSWORD."
        )

    retry_policy = RetryPolicy(
        timeout_seconds=timeout,
        max_attempts=retry_attempts,
        backoff_seconds=retry_backoff_seconds,
        max_backoff_seconds=retry_backoff_max_seconds,
        max_redirects=max_redirects,
    )

    logger.debug(
        "Resolved Odoo client config url=%s db=%s user=%s timeout=%s attempts=%s verify_ssl=%s",
        config["url"],
        config["db"],
        resolved_username,
        timeout,
        retry_attempts,
        verify_ssl,
    )

    return OdooClient(
        url=config["url"],
        db=config["db"],
        username=resolved_username,
        password=resolved_password,
        timeout=timeout,
        verify_ssl=verify_ssl,
        retry_policy=retry_policy,
    )
