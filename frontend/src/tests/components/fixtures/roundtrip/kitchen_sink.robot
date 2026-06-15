*** Settings ***
Documentation     Kitchen-sink suite exercising tricky RF syntax for round-trip.
Library           Collections
Library           Browser
Suite Setup       Log    suite start
Force Tags        regression

*** Variables ***
${BASE_URL}       https://example.com
${HEADLESS}       false
@{COLORS}         red    green    blue
&{USER}           name=alice    role=admin

*** Test Cases ***
# A comment sitting above the first test case.
Login Flow
    [Documentation]    Multi-line doc
    ...                second line of the doc
    [Tags]    smoke    auth
    New Browser    chromium    headless=${HEADLESS}
    New Page    ${BASE_URL}/login    wait_until=domcontentloaded
    Fill Text    \#user    alice    # inline comment after a real step
    ${token}=    Get Text    css=.token
    IF    ${token}
        Log    got token
        FOR    ${c}    IN    @{COLORS}
            Log    ${c}
        END
    ELSE
        Log    no token
    END

Env Var Test
    ${home}=    Get Environment Variable    %{HOME=/tmp}
    Should Not Be Empty    ${home}

*** Keywords ***
Open Site
    [Arguments]    ${url}
    New Page    ${url}    wait_until=domcontentloaded
    RETURN    ${url}
