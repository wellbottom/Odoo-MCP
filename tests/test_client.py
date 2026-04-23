import xmlrpc.client

from odoo_mcp.server.client import RedirectTransport, RetryPolicy
from odoo_mcp.server.errors import error_to_payload


def test_redirect_transport_retries_retryable_protocol_errors(monkeypatch):
    attempts = []
    responses = iter(
        [
            xmlrpc.client.ProtocolError(
                "https://odoo.example.com/xmlrpc/2/object",
                503,
                "Service Unavailable",
                {},
            ),
            "ok",
        ]
    )

    def fake_request(self, host, handler, request_body, verbose):
        attempts.append((host, handler))
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(xmlrpc.client.Transport, "request", fake_request)

    transport = RedirectTransport(
        use_https=True,
        verify_ssl=True,
        retry_policy=RetryPolicy(
            timeout_seconds=5,
            max_attempts=2,
            backoff_seconds=0,
            max_backoff_seconds=0,
            max_redirects=5,
        ),
    )

    assert transport.request("odoo.example.com", "/xmlrpc/2/object", b"", False) == "ok"
    assert attempts == [
        ("odoo.example.com", "/xmlrpc/2/object"),
        ("odoo.example.com", "/xmlrpc/2/object"),
    ]


def test_error_to_payload_classifies_access_fault():
    payload = error_to_payload(
        xmlrpc.client.Fault(
            1,
            "You are not allowed to access 'Payslip Batches' (hr.payslip.run) records.",
        ),
        model="hr.payslip.run",
        method="search_read",
    )

    assert payload["success"] is False
    assert payload["error_category"] == "authorization_error"
    assert payload["retryable"] is False
    assert payload["model"] == "hr.payslip.run"
    assert payload["method"] == "search_read"
