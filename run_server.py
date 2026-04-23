#!/usr/bin/env python
"""
Standalone runner for the Odoo MCP HTTP server.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from odoo_mcp.server.http import get_uvicorn_run_kwargs, run_http_server


def setup_logging() -> logging.Logger:
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"mcp_server_{timestamp}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def main() -> int:
    logger = setup_logging()

    try:
        run_kwargs = get_uvicorn_run_kwargs()
        transport_scheme = "HTTPS" if "ssl_certfile" in run_kwargs else "HTTP"

        logger.info("=== ODOO MCP SERVER STARTING ===")
        logger.info("Python version: %s", sys.version)
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith("ODOO_") or key.startswith("MCP_"):
                if "PASSWORD" in key:
                    logger.info("  %s: ***hidden***", key)
                else:
                    logger.info("  %s: %s", key, value)

        logger.info(
            "Starting Odoo MCP server with streamable %s transport on %s:%s",
            transport_scheme,
            run_kwargs["host"],
            run_kwargs["port"],
        )
        run_http_server(run_kwargs=run_kwargs)
        logger.info("MCP server stopped normally")
        return 0
    except Exception as exc:
        logger.error("Fatal error: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
