"""System and user prompt templates for AI generation."""

SYSTEM_PROMPT_GENERATE = """\
You are a Robot Framework test automation expert. Your task is to generate \
a complete, syntactically correct .robot file from a YAML test specification.

## Robot Framework Syntax Rules
- Sections start with `*** <Name> ***` (e.g. `*** Settings ***`, `*** Variables ***`, \
`*** Test Cases ***`, `*** Keywords ***`)
- Use 4 spaces (or 2+ spaces) as separator between keyword and arguments
- Test case names are left-aligned under `*** Test Cases ***`
- Keywords and steps are indented with 4 spaces
- Tags are set via `[Tags]` inside a test case or `Force Tags` in Settings
- Setup/Teardown use `[Setup]` / `[Teardown]` inside test cases or \
`Test Setup` / `Test Teardown` in Settings
- Variables: `${scalar}`, `@{list}`, `&{dict}`
- Comments start with `#`

## Output Requirements
- Output ONLY the .robot file content, no explanations or markdown fences
- Include `*** Settings ***` with Library imports from the spec metadata
- Include `*** Variables ***` if needed
- Include `*** Test Cases ***` with all test cases from all test sets
- Include `*** Keywords ***` for reusable steps
- Use descriptive keyword names that match the natural-language steps
- Add `[Tags]` from the spec's tags
- Add `[Setup]` / `[Teardown]` from the spec's test set setup/teardown
- Add `[Documentation]` from the spec's descriptions
- Generate sensible Robot Framework keywords for each natural-language step
- Steps can be simple strings or structured objects with action/data/expected_result fields
- For structured steps, focus on the 'action' field to generate the keyword
- Ignore external_id and preconditions fields (they are for Xray/test management only)
"""

SYSTEM_PROMPT_REVERSE = """\
You are a Robot Framework test automation expert. Your task is to analyze \
a .robot file and produce a YAML test specification in the .roboscope v2 format.

## .roboscope v2 YAML Format
```yaml
version: "2"
metadata:
  title: "<descriptive title>"
  author: ""
  created: "<today's date>"
  last_generated: null
  generation_hash: null
  target_file: "<relative path to the .robot file>"
  libraries:
    - <Library1>
    - <Library2>

test_sets:
  - name: "<group name>"
    description: "<what this group tests>"
    tags: [tag1, tag2]
    setup: "<setup keyword or null>"
    teardown: "<teardown keyword or null>"
    test_cases:
      - name: "<test case name>"
        description: "<human-readable description of what the test does>"
        priority: high|medium|low
        steps:
          - "<natural language step 1>"
          - "<natural language step 2>"
        expected_result: "<what should happen>"
```

## Instructions
- Always use version: "2"
- Group related test cases into test_sets by analyzing tags, setup/teardown, and naming
- Convert Robot Framework keywords back into natural-language step descriptions
- Infer priority from tags or naming conventions (smoke → high, etc.)
- Extract libraries from *** Settings ***
- Steps should be simple strings (natural language descriptions)
- Output ONLY valid YAML, no explanations or markdown fences
"""


SYSTEM_PROMPT_ANALYZE = """\
You are a Robot Framework test failure analyst. Given a test report with failed \
tests, provide a thorough root-cause analysis and actionable fix suggestions.

## Your Analysis Should Include

1. **Root Cause Analysis** — For each failed test, identify the most likely cause:
   - Configuration issues (missing libraries, wrong paths, environment problems)
   - Test logic errors (wrong selectors, timing issues, incorrect assertions)
   - Application bugs (unexpected behavior, API changes, UI changes)
   - Infrastructure issues (network, database, service availability)

2. **Pattern Detection** — Look across all failures for common patterns:
   - Same error message across multiple tests
   - Same suite having multiple failures
   - Timing-related failures (short duration = early crash, long duration = timeout)
   - Tag-based patterns (certain categories failing together)

3. **Suggested Fixes** — Provide specific, actionable fix suggestions:
   - Code-level fixes where possible
   - Configuration changes needed
   - Environment setup steps

4. **Priority Ranking** — Classify each issue:
   - CRITICAL: Blocks entire test suite or indicates production bug
   - HIGH: Multiple tests affected, likely real regression
   - MEDIUM: Individual test failures, possibly flaky
   - LOW: Minor issues, cosmetic failures

## Output Format
- Use clear markdown with headers, bullet points, and code blocks
- Start with a brief executive summary
- Group related failures together
- End with a prioritized action list
"""


def build_analyze_user_prompt(
    report_summary: dict,
    failed_tests: list[dict],
) -> str:
    """Build the user prompt for failure analysis.

    Args:
        report_summary: dict with total_tests, passed, failed, skipped, duration keys.
        failed_tests: list of dicts with name, suite, error_message, tags, duration keys.
    """
    prompt = "## Test Report Summary\n\n"
    prompt += f"- **Total Tests**: {report_summary['total_tests']}\n"
    prompt += f"- **Passed**: {report_summary['passed']}\n"
    prompt += f"- **Failed**: {report_summary['failed']}\n"
    prompt += f"- **Skipped**: {report_summary['skipped']}\n"
    prompt += f"- **Total Duration**: {report_summary['duration']:.1f}s\n"
    prompt += f"- **Pass Rate**: {report_summary['pass_rate']:.1f}%\n\n"

    prompt += f"## Failed Tests ({len(failed_tests)})\n\n"

    for i, test in enumerate(failed_tests, 1):
        prompt += f"### {i}. {test['name']}\n"
        prompt += f"- **Suite**: {test['suite']}\n"
        prompt += f"- **Duration**: {test['duration']:.2f}s\n"
        if test.get('tags'):
            prompt += f"- **Tags**: {test['tags']}\n"
        prompt += f"- **Error Message**:\n```\n{test['error_message'] or 'No error message'}\n```\n\n"

    prompt += "Please analyze the failures above and provide root-cause analysis, "
    prompt += "pattern detection, fix suggestions, and priority ranking."

    return prompt


def build_generate_user_prompt(
    spec_content: str,
    existing_robot: str | None = None,
) -> str:
    """Build the user prompt for spec→robot generation."""
    prompt = f"Generate a complete .robot file from this specification:\n\n{spec_content}"
    if existing_robot:
        prompt += (
            "\n\n--- EXISTING .robot FILE (preserve patterns where appropriate) ---\n\n"
            + existing_robot
        )
    return prompt


def build_reverse_user_prompt(robot_content: str) -> str:
    """Build the user prompt for robot→spec extraction."""
    return (
        "Analyze this .robot file and produce a .roboscope v2 YAML specification:\n\n"
        + robot_content
    )


def enrich_generate_prompt(
    spec_content: str,
    existing_robot: str | None = None,
    keyword_docs: list[dict] | None = None,
    library_recommendations: list[str] | None = None,
) -> str:
    """Build an enriched user prompt for spec→robot generation.

    When rf-mcp data is available, appends RF keyword documentation and
    library recommendations to help the LLM generate better .robot code.

    rf-mcp by Many Kasiriha — https://github.com/manykarim/rf-mcp
    """
    prompt = build_generate_user_prompt(spec_content, existing_robot)

    enrichment_parts: list[str] = []

    if keyword_docs:
        docs_text = "\n".join(
            f"- {kw.get('name', 'Unknown')} ({kw.get('library', '?')}): "
            f"{kw.get('doc', 'No documentation')}"
            for kw in keyword_docs
        )
        enrichment_parts.append(
            f"## Relevant Robot Framework Keywords\n"
            f"(sourced via rf-mcp by Many Kasiriha)\n\n{docs_text}"
        )

    if library_recommendations:
        libs_text = ", ".join(library_recommendations)
        enrichment_parts.append(
            f"## Recommended Libraries\n"
            f"(sourced via rf-mcp by Many Kasiriha)\n\n"
            f"Consider using: {libs_text}"
        )

    if enrichment_parts:
        prompt += "\n\n--- RF KNOWLEDGE ENRICHMENT ---\n\n"
        prompt += "\n\n".join(enrichment_parts)

    return prompt
