"""Library-Name to PyPI-Package mapping and built-in recognition for Robot Framework."""

# Robot Framework built-in libraries (no pip install needed)
BUILTIN_LIBRARIES: set[str] = {
    "BuiltIn",
    "Collections",
    "String",
    "OperatingSystem",
    "Process",
    "DateTime",
    "XML",
    "Dialogs",
    "Screenshot",
    "Telnet",
    "Remote",
}

# Known library name -> PyPI package name mapping
LIBRARY_TO_PYPI: dict[str, str] = {
    "SeleniumLibrary": "robotframework-seleniumlibrary",
    "Browser": "robotframework-browser",
    "RequestsLibrary": "robotframework-requests",
    "DatabaseLibrary": "robotframework-databaselibrary",
    "SSHLibrary": "robotframework-sshlibrary",
    "FtpLibrary": "robotframework-ftplibrary",
    "AppiumLibrary": "robotframework-appiumlibrary",
    "ArchiveLibrary": "robotframework-archivelibrary",
    "JSONLibrary": "robotframework-jsonlibrary",
    "ExcelLibrary": "robotframework-excellibrary",
    "ImapLibrary": "robotframework-imaplibrary",
    "PdfLibrary": "robotframework-pdflibrary",
    "CryptoLibrary": "robotframework-crypto",
    "DataDriver": "robotframework-datadriver",
    "Pabot": "robotframework-pabot",
    "RPA": "rpaframework",
    "RESTinstance": "RESTinstance",
    "Selenium2Library": "robotframework-selenium2library",
    "WhiteLibrary": "robotframework-whitelibrary",
    "SikuliLibrary": "robotframework-sikulilibrary",
    "OTPLibrary": "robotframework-otp",
    "DebugLibrary": "robotframework-debuglibrary",
}


def resolve_pypi_package(library_name: str) -> str | None:
    """Resolve a Robot Framework library name to its PyPI package name.

    Returns None for built-in libraries and path-based imports.
    Uses the known mapping first, then falls back to a heuristic.
    """
    # Skip built-in libraries
    if library_name in BUILTIN_LIBRARIES:
        return None

    # Skip path-based imports (contains /, \, or .py)
    if "/" in library_name or "\\" in library_name or library_name.endswith(".py"):
        return None

    # Skip relative imports (e.g. .MyLibrary, ..utils.MyLib)
    if library_name.startswith("."):
        return None

    # Known mapping lookup
    if library_name in LIBRARY_TO_PYPI:
        return LIBRARY_TO_PYPI[library_name]

    # Heuristic fallback: robotframework-{name_lower}
    return f"robotframework-{library_name.lower()}"
