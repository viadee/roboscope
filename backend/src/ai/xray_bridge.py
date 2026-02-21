"""Xray JSON ↔ .roboscope v2 conversion bridge.

Converts between .roboscope v2 YAML specs and Xray JSON import/export format,
enabling direct integration with Xray/Jira test management.
"""

from datetime import datetime, timezone


def roboscope_to_xray(spec: dict) -> dict:
    """Convert a .roboscope v2 spec dict to Xray JSON import format.

    Mapping:
    - metadata.external_id → info.testPlanKey
    - test_case.external_id → tests[].testKey
    - test_case.name → testInfo.summary
    - test_case.priority → testInfo.priority
    - test_case.preconditions → testInfo.precondition
    - String step → {fields: {Action: step}}
    - Object step → {fields: {Action, Data, Expected Result}}
    - test_set.tags → labels
    - metadata.libraries → included in test description
    """
    metadata = spec.get("metadata", {})
    test_sets = spec.get("test_sets", [])

    info: dict = {}
    test_plan_key = metadata.get("external_id")
    if test_plan_key:
        info["testPlanKey"] = test_plan_key

    info["summary"] = metadata.get("title", "Untitled")

    libraries = metadata.get("libraries", [])

    tests: list[dict] = []

    for ts in test_sets:
        ts_tags = ts.get("tags", [])
        ts_external_id = ts.get("external_id")
        ts_preconditions = ts.get("preconditions", [])

        for tc in ts.get("test_cases", []):
            test_entry: dict = {}

            # Test key from external_id
            tc_external_id = tc.get("external_id")
            if tc_external_id:
                test_entry["testKey"] = tc_external_id

            # Test info
            test_info: dict = {
                "summary": tc.get("name", ""),
            }

            # Description — combine test case description + library info
            desc_parts: list[str] = []
            if tc.get("description"):
                desc_parts.append(tc["description"])
            if ts.get("description"):
                desc_parts.append(f"Test Set: {ts.get('name', '')}: {ts['description']}")
            if libraries:
                desc_parts.append(f"Libraries: {', '.join(libraries)}")
            if desc_parts:
                test_info["description"] = "\n".join(desc_parts)

            # Priority mapping
            priority = tc.get("priority", "medium")
            priority_map = {"high": "High", "medium": "Medium", "low": "Low"}
            test_info["priority"] = priority_map.get(priority, "Medium")

            # Type
            test_info["type"] = "Manual"

            # Labels from tags
            all_tags = list(ts_tags) + tc.get("tags", [])
            if all_tags:
                test_info["labels"] = all_tags

            # Preconditions (merge test-set and test-case level)
            all_preconditions = list(ts_preconditions) + tc.get("preconditions", [])
            if all_preconditions:
                test_info["precondition"] = "\n".join(all_preconditions)

            # Test set folder info
            if ts_external_id:
                test_info["testSetKey"] = ts_external_id

            test_entry["testInfo"] = test_info

            # Steps
            steps = tc.get("steps", [])
            if steps:
                xray_steps: list[dict] = []
                for step in steps:
                    if isinstance(step, str):
                        xray_steps.append({
                            "fields": {"Action": step}
                        })
                    elif isinstance(step, dict):
                        fields: dict = {"Action": step.get("action", "")}
                        if step.get("data"):
                            fields["Data"] = step["data"]
                        if step.get("expected_result"):
                            fields["Expected Result"] = step["expected_result"]
                        xray_steps.append({"fields": fields})
                test_entry["steps"] = xray_steps

            tests.append(test_entry)

    result: dict = {"info": info, "tests": tests}
    return result


def xray_to_roboscope(xray_data: dict) -> dict:
    """Convert Xray JSON export to a .roboscope v2 spec dict.

    Mapping:
    - tests[].testKey → test_case.external_id
    - testInfo.summary → test_case.name
    - tests[].steps[].fields.Action → step action
    - If only Action → simple string step
    - If Data or Expected Result → structured step object
    """
    info = xray_data.get("info", {})

    metadata: dict = {
        "title": info.get("summary", "Imported from Xray"),
        "author": "",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "last_generated": None,
        "generation_hash": None,
        "target_file": "tests/imported.robot",
        "libraries": [],
    }

    # Test plan key → external_id
    test_plan_key = info.get("testPlanKey")
    if test_plan_key:
        metadata["external_id"] = test_plan_key

    tests = xray_data.get("tests", [])

    # Group tests by testSetKey if present, otherwise into a default group
    groups: dict[str, list[dict]] = {}
    for test in tests:
        test_info = test.get("testInfo", {})
        set_key = test_info.get("testSetKey", "__default__")
        if set_key not in groups:
            groups[set_key] = []
        groups[set_key].append(test)

    test_sets: list[dict] = []
    for group_key, group_tests in groups.items():
        ts: dict = {
            "name": group_key if group_key != "__default__" else "Imported Tests",
            "description": "",
            "tags": [],
            "setup": None,
            "teardown": None,
            "test_cases": [],
        }

        if group_key != "__default__":
            ts["external_id"] = group_key

        for test in group_tests:
            test_info = test.get("testInfo", {})
            tc: dict = {
                "name": test_info.get("summary", "Unnamed"),
                "description": test_info.get("description", ""),
                "priority": _map_xray_priority(test_info.get("priority", "Medium")),
                "steps": [],
                "expected_result": "",
            }

            # External ID
            test_key = test.get("testKey")
            if test_key:
                tc["external_id"] = test_key

            # Labels → tags (first test case sets test-set tags)
            labels = test_info.get("labels", [])
            if labels:
                # Add unique labels to test set tags
                for label in labels:
                    if label not in ts["tags"]:
                        ts["tags"].append(label)

            # Preconditions
            precondition = test_info.get("precondition", "")
            if precondition:
                tc["preconditions"] = [
                    line.strip()
                    for line in precondition.split("\n")
                    if line.strip()
                ]

            # Steps
            for step_data in test.get("steps", []):
                fields = step_data.get("fields", {})
                action = fields.get("Action", "")
                data = fields.get("Data", "")
                expected = fields.get("Expected Result", "")

                if data or expected:
                    # Structured step
                    step_obj: dict = {"action": action}
                    if data:
                        step_obj["data"] = data
                    if expected:
                        step_obj["expected_result"] = expected
                    tc["steps"].append(step_obj)
                else:
                    # Simple string step
                    tc["steps"].append(action)

            ts["test_cases"].append(tc)

        test_sets.append(ts)

    return {
        "version": "2",
        "metadata": metadata,
        "test_sets": test_sets,
    }


def _map_xray_priority(priority: str) -> str:
    """Map Xray priority string to .roboscope priority."""
    mapping = {
        "High": "high",
        "Highest": "high",
        "Critical": "high",
        "Medium": "medium",
        "Normal": "medium",
        "Low": "low",
        "Lowest": "low",
    }
    return mapping.get(priority, "medium")
