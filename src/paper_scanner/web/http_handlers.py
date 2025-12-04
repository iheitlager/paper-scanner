"""HTTP error handlers for PDF Browser application."""

import logging
from typing import Any, Dict, Tuple

from flask import jsonify

from .exceptions import PDFBrowserException

logger = logging.getLogger(__name__)


def register_error_handlers(app: Any) -> None:
    """Register all HTTP error handlers with the Flask app.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(PDFBrowserException)
    def handle_pdf_browser_exception(error: PDFBrowserException) -> Tuple[Dict[str, Any], int]:
        """Handle custom PDF Browser exceptions.

        Args:
            error: PDFBrowserException instance

        Returns:
            JSON response with error details and status code
        """
        logger.error(f"{error.__class__.__name__}: {error.message}")
        return jsonify({"success": False, "error": error.message}), error.status_code

    @app.errorhandler(400)
    def handle_bad_request(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle 400 Bad Request errors."""
        return jsonify({"success": False, "error": "Invalid request"}), 400

    @app.errorhandler(404)
    def handle_not_found(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle 404 Not Found errors."""
        return jsonify({"success": False, "error": "Resource not found"}), 404

    @app.errorhandler(500)
    def handle_internal_error(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle 500 Internal Server errors."""
        logger.error(f"Internal server error: {error}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
