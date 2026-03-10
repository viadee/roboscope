"""Tests for library_mapping: PyPI package resolution and built-in detection."""

import pytest

from src.explorer.library_mapping import (
    BUILTIN_LIBRARIES,
    LIBRARY_TO_PYPI,
    identify_rf_libraries,
    resolve_pypi_package,
)


class TestBuiltinLibraries:
    def test_builtin_set_contains_core_libraries(self):
        assert "BuiltIn" in BUILTIN_LIBRARIES
        assert "Collections" in BUILTIN_LIBRARIES
        assert "String" in BUILTIN_LIBRARIES
        assert "OperatingSystem" in BUILTIN_LIBRARIES
        assert "Process" in BUILTIN_LIBRARIES
        assert "DateTime" in BUILTIN_LIBRARIES

    def test_builtin_set_contains_additional_libraries(self):
        assert "XML" in BUILTIN_LIBRARIES
        assert "Dialogs" in BUILTIN_LIBRARIES
        assert "Screenshot" in BUILTIN_LIBRARIES
        assert "Telnet" in BUILTIN_LIBRARIES
        assert "Remote" in BUILTIN_LIBRARIES


class TestLibraryToPypi:
    def test_known_mappings_exist(self):
        assert "SeleniumLibrary" in LIBRARY_TO_PYPI
        assert "Browser" in LIBRARY_TO_PYPI
        assert "RequestsLibrary" in LIBRARY_TO_PYPI

    def test_known_mapping_values(self):
        assert LIBRARY_TO_PYPI["SeleniumLibrary"] == "robotframework-seleniumlibrary"
        assert LIBRARY_TO_PYPI["Browser"] == "robotframework-browser"
        assert LIBRARY_TO_PYPI["RequestsLibrary"] == "robotframework-requests"


class TestResolvePypiPackage:
    def test_builtin_returns_none(self):
        assert resolve_pypi_package("BuiltIn") is None
        assert resolve_pypi_package("Collections") is None
        assert resolve_pypi_package("String") is None

    def test_path_based_import_with_slash(self):
        assert resolve_pypi_package("libs/MyLibrary.py") is None

    def test_path_based_import_with_backslash(self):
        assert resolve_pypi_package("libs\\MyLibrary.py") is None

    def test_path_based_import_with_py_extension(self):
        assert resolve_pypi_package("MyLibrary.py") is None

    def test_relative_import_skipped(self):
        assert resolve_pypi_package(".MyLibrary") is None
        assert resolve_pypi_package("..utils.MyLib") is None

    def test_known_mapping_lookup(self):
        assert resolve_pypi_package("SeleniumLibrary") == "robotframework-seleniumlibrary"
        assert resolve_pypi_package("Browser") == "robotframework-browser"
        assert resolve_pypi_package("RequestsLibrary") == "robotframework-requests"
        assert resolve_pypi_package("SSHLibrary") == "robotframework-sshlibrary"

    def test_heuristic_fallback_for_unknown_library(self):
        result = resolve_pypi_package("SomeCustomLibrary")
        assert result == "robotframework-somecustomlibrary"

    def test_heuristic_fallback_lowercases(self):
        result = resolve_pypi_package("MyLib")
        assert result == "robotframework-mylib"


class TestIdentifyRfLibraries:
    def test_known_package(self):
        packages = [{"name": "robotframework-seleniumlibrary", "version": "6.2.0"}]
        result = identify_rf_libraries(packages)
        assert len(result) == 1
        assert result[0]["library_name"] == "SeleniumLibrary"
        assert result[0]["source"] == "known"
        assert result[0]["version"] == "6.2.0"

    def test_heuristic_package(self):
        packages = [{"name": "robotframework-excelreader", "version": "1.0.0"}]
        result = identify_rf_libraries(packages)
        assert len(result) == 1
        assert result[0]["library_name"] == "Excelreader"
        assert result[0]["source"] == "heuristic"

    def test_robotframework_itself_excluded(self):
        packages = [{"name": "robotframework", "version": "7.0"}]
        result = identify_rf_libraries(packages)
        assert len(result) == 0

    def test_non_rf_package_excluded(self):
        packages = [
            {"name": "requests", "version": "2.31.0"},
            {"name": "flask", "version": "3.0.0"},
        ]
        result = identify_rf_libraries(packages)
        assert len(result) == 0

    def test_rpaframework_detected(self):
        packages = [{"name": "rpaframework", "version": "28.0.0"}]
        result = identify_rf_libraries(packages)
        assert len(result) == 1
        assert result[0]["library_name"] == "RPA"
        assert result[0]["source"] == "known"

    def test_mixed_packages(self):
        packages = [
            {"name": "robotframework", "version": "7.0"},
            {"name": "robotframework-browser", "version": "18.0.0"},
            {"name": "requests", "version": "2.31.0"},
            {"name": "robotframework-customlib", "version": "0.1.0"},
        ]
        result = identify_rf_libraries(packages)
        assert len(result) == 2
        names = {r["library_name"] for r in result}
        assert "Browser" in names
        assert "Customlib" in names

    def test_empty_input(self):
        assert identify_rf_libraries([]) == []
