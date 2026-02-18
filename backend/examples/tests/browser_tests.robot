*** Settings ***
Documentation     Browser tests using Robot Framework Browser Library (Playwright-based)
Library           Browser

*** Test Cases ***
Open Browser and Check Page Title
    [Documentation]    Opens a local page and verifies the page title
    New Browser    chromium    headless=True
    New Page    file://${CURDIR}/test.html
    ${title}=    Get Title
    Should Contain    ${title}    Test Page
    Close Browser

Navigate and Find Element
    [Documentation]    Opens a page and verifies specific elements exist
    New Browser    chromium    headless=True
    New Page    file://${CURDIR}/test.html
    Get Text    h1    ==    Example Domain
    ${paragraph}=    Get Text    p
    Should Contain    ${paragraph}    This domain is for use in illustrative examples
    Close Browser

Interact with Page Elements
    [Documentation]    Tests interaction with various page elements
    New Browser    chromium    headless=True
    New Page    file://${CURDIR}/test.html
    Click    id=test-button
    Type Text    id=test-input    Robot Framework Test
    ${input_value}=    Get Property    id=test-input    value
    Should Be Equal    ${input_value}    Robot Framework Test
    Close Browser
