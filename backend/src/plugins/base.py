"""Abstract base classes for the plugin system."""

from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    """Base interface all plugins must implement."""

    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    plugin_type: str = ""  # analyzer, runner, integration, kpi

    @abstractmethod
    def initialize(self, config: dict | None = None) -> None:
        """Initialize the plugin with optional config."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources."""
        ...


class AnalyzerPlugin(BasePlugin):
    """Plugin that extends report analysis."""

    plugin_type = "analyzer"

    @abstractmethod
    def analyze(self, report_data: dict) -> dict:
        """Analyze a report and return additional insights.

        Args:
            report_data: Dict with report info including test_results.

        Returns:
            Dict with analysis results.
        """
        ...


class RunnerPlugin(BasePlugin):
    """Plugin that provides a new runner type (e.g., Kubernetes, SSH)."""

    plugin_type = "runner"

    @abstractmethod
    def execute(
        self,
        repo_path: str,
        target_path: str,
        output_dir: str,
        config: dict | None = None,
    ) -> dict:
        """Execute tests and return results."""
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Cancel a running execution."""
        ...


class IntegrationPlugin(BasePlugin):
    """Plugin for external system integration (Slack, Jira, Teams, etc.)."""

    plugin_type = "integration"

    @abstractmethod
    def on_run_started(self, run_data: dict) -> None:
        """Called when a test run starts."""
        ...

    @abstractmethod
    def on_run_completed(self, run_data: dict, report_data: dict | None = None) -> None:
        """Called when a test run completes."""
        ...

    @abstractmethod
    def on_run_failed(self, run_data: dict, error: str) -> None:
        """Called when a test run fails."""
        ...


class KpiPlugin(BasePlugin):
    """Plugin for custom KPI calculations."""

    plugin_type = "kpi"

    @abstractmethod
    def compute(self, test_results: list[dict]) -> dict:
        """Compute custom KPIs from test results.

        Args:
            test_results: List of test result dicts.

        Returns:
            Dict with KPI name/value pairs.
        """
        ...
