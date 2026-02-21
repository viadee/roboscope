"""Tests for the Xray bridge conversion module."""

from src.ai.xray_bridge import roboscope_to_xray, xray_to_roboscope


class TestRoboscopeToXray:
    def test_basic_conversion(self):
        """Convert a basic .roboscope spec to Xray JSON."""
        spec = {
            "version": "2",
            "metadata": {
                "title": "Login Tests",
                "target_file": "tests/login.robot",
                "external_id": "PROJ-100",
                "libraries": ["SeleniumLibrary"],
            },
            "test_sets": [
                {
                    "name": "Auth",
                    "tags": ["smoke"],
                    "external_id": "PROJ-50",
                    "preconditions": ["System is running"],
                    "test_cases": [
                        {
                            "name": "Valid Login",
                            "description": "Test valid login",
                            "priority": "high",
                            "external_id": "PROJ-101",
                            "preconditions": ["User is on login page"],
                            "steps": [
                                "Navigate to login page",
                                {
                                    "action": "Enter credentials",
                                    "data": "user: admin",
                                    "expected_result": "Fields filled",
                                },
                            ],
                            "expected_result": "User is logged in",
                        }
                    ],
                }
            ],
        }

        result = roboscope_to_xray(spec)

        assert result["info"]["testPlanKey"] == "PROJ-100"
        assert result["info"]["summary"] == "Login Tests"

        tests = result["tests"]
        assert len(tests) == 1
        test = tests[0]
        assert test["testKey"] == "PROJ-101"
        assert test["testInfo"]["summary"] == "Valid Login"
        assert test["testInfo"]["priority"] == "High"
        assert "System is running" in test["testInfo"]["precondition"]
        assert "User is on login page" in test["testInfo"]["precondition"]

        # Steps
        steps = test["steps"]
        assert len(steps) == 2
        assert steps[0]["fields"]["Action"] == "Navigate to login page"
        assert "Data" not in steps[0]["fields"]
        assert steps[1]["fields"]["Action"] == "Enter credentials"
        assert steps[1]["fields"]["Data"] == "user: admin"
        assert steps[1]["fields"]["Expected Result"] == "Fields filled"

    def test_tags_as_labels(self):
        """Tags should be converted to labels."""
        spec = {
            "version": "2",
            "metadata": {"title": "Tests", "target_file": "t.robot"},
            "test_sets": [
                {
                    "name": "Set1",
                    "tags": ["smoke", "regression"],
                    "test_cases": [{"name": "TC1", "steps": []}],
                }
            ],
        }
        result = roboscope_to_xray(spec)
        assert result["tests"][0]["testInfo"]["labels"] == ["smoke", "regression"]

    def test_no_external_id(self):
        """Conversion should work without external_id."""
        spec = {
            "version": "2",
            "metadata": {"title": "Tests", "target_file": "t.robot"},
            "test_sets": [
                {
                    "name": "Set1",
                    "test_cases": [
                        {"name": "TC1", "priority": "low", "steps": ["Do something"]}
                    ],
                }
            ],
        }
        result = roboscope_to_xray(spec)
        assert "testPlanKey" not in result["info"]
        assert "testKey" not in result["tests"][0]
        assert result["tests"][0]["testInfo"]["priority"] == "Low"

    def test_empty_spec(self):
        """Empty spec should produce valid but empty output."""
        spec = {"version": "2", "metadata": {"title": "Empty"}, "test_sets": []}
        result = roboscope_to_xray(spec)
        assert result["tests"] == []


class TestXrayToRoboscope:
    def test_basic_import(self):
        """Convert Xray JSON to .roboscope v2 spec."""
        xray_data = {
            "info": {
                "summary": "Imported Tests",
                "testPlanKey": "PROJ-100",
            },
            "tests": [
                {
                    "testKey": "PROJ-101",
                    "testInfo": {
                        "summary": "Valid Login",
                        "description": "Login test",
                        "priority": "High",
                        "labels": ["smoke"],
                        "precondition": "User is on login page",
                    },
                    "steps": [
                        {"fields": {"Action": "Navigate to login page"}},
                        {
                            "fields": {
                                "Action": "Enter credentials",
                                "Data": "user: admin",
                                "Expected Result": "Fields filled",
                            }
                        },
                    ],
                }
            ],
        }

        result = xray_to_roboscope(xray_data)

        assert result["version"] == "2"
        assert result["metadata"]["external_id"] == "PROJ-100"
        assert result["metadata"]["title"] == "Imported Tests"

        ts = result["test_sets"]
        assert len(ts) == 1
        tc = ts[0]["test_cases"][0]
        assert tc["external_id"] == "PROJ-101"
        assert tc["name"] == "Valid Login"
        assert tc["priority"] == "high"
        assert tc["preconditions"] == ["User is on login page"]

        # Steps: first is string, second is structured
        steps = tc["steps"]
        assert len(steps) == 2
        assert steps[0] == "Navigate to login page"
        assert isinstance(steps[1], dict)
        assert steps[1]["action"] == "Enter credentials"
        assert steps[1]["data"] == "user: admin"
        assert steps[1]["expected_result"] == "Fields filled"

    def test_grouped_by_test_set_key(self):
        """Tests with testSetKey should be grouped into separate test sets."""
        xray_data = {
            "info": {"summary": "Test Suite"},
            "tests": [
                {
                    "testKey": "TC-1",
                    "testInfo": {"summary": "Test A", "testSetKey": "TS-1"},
                    "steps": [],
                },
                {
                    "testKey": "TC-2",
                    "testInfo": {"summary": "Test B", "testSetKey": "TS-2"},
                    "steps": [],
                },
            ],
        }

        result = xray_to_roboscope(xray_data)
        assert len(result["test_sets"]) == 2
        names = {ts["name"] for ts in result["test_sets"]}
        assert "TS-1" in names
        assert "TS-2" in names
