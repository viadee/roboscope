"""Built-in console logger integration plugin (example)."""

import logging

from src.plugins.base import IntegrationPlugin

logger = logging.getLogger(__name__)


class ConsoleLoggerPlugin(IntegrationPlugin):
    """Simple plugin that logs run events to the console. Serves as an example."""

    name = "console_logger"
    version = "0.1.0"
    description = "Logs test run events to the application console"

    def initialize(self, config: dict | None = None) -> None:
        self._log_level = (config or {}).get("log_level", "INFO")
        logger.info("ConsoleLoggerPlugin initialized")

    def shutdown(self) -> None:
        logger.info("ConsoleLoggerPlugin shutdown")

    def on_run_started(self, run_data: dict) -> None:
        logger.info(f"[ConsoleLogger] Run started: #{run_data.get('id')} - {run_data.get('target_path')}")

    def on_run_completed(self, run_data: dict, report_data: dict | None = None) -> None:
        status = run_data.get("status", "unknown")
        total = report_data.get("total_tests", 0) if report_data else 0
        passed = report_data.get("passed_tests", 0) if report_data else 0
        logger.info(
            f"[ConsoleLogger] Run completed: #{run_data.get('id')} - "
            f"{status} ({passed}/{total} passed)"
        )

    def on_run_failed(self, run_data: dict, error: str) -> None:
        logger.warning(
            f"[ConsoleLogger] Run failed: #{run_data.get('id')} - {error}"
        )
