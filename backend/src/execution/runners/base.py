"""Abstract base class for test runners."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class RunResult:
    """Result of a test execution."""

    success: bool
    exit_code: int = 0
    output_dir: str = ""
    output_xml_path: str = ""
    log_html_path: str = ""
    report_html_path: str = ""
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    duration_seconds: float = 0.0


class AbstractRunner(ABC):
    """Base interface for all test runners."""

    @abstractmethod
    def prepare(self, repo_path: str, target_path: str, env_config: dict | None = None) -> None:
        """Prepare the execution environment (venv, container, etc.)."""
        ...

    @abstractmethod
    def execute(
        self,
        repo_path: str,
        target_path: str,
        output_dir: str,
        variables: dict | None = None,
        tags_include: str | None = None,
        tags_exclude: str | None = None,
        timeout: int = 3600,
        on_output: Callable[[str], None] | None = None,
    ) -> RunResult:
        """Execute tests and return the result."""
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Cancel a running execution."""
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources after execution."""
        ...
