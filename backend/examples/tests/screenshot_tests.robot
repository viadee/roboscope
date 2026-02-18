*** Settings ***
Documentation     Screenshot tests demonstrating screenshot capabilities
Library           OperatingSystem
Library           Screenshot

*** Test Cases ***
Create and Verify Screenshot Directory
    [Documentation]    Tests creating a directory for screenshots
    Create Directory    ${CURDIR}/../screenshots
    Directory Should Exist    ${CURDIR}/../screenshots

File System Screenshot Test
    [Documentation]    Tests file system operations for screenshot handling
    ${screenshot_path}=    Set Variable    ${CURDIR}/../screenshots/test_screenshot.txt
    Create File    ${screenshot_path}    Test screenshot data
    Take Screenshot
    File Should Exist    ${screenshot_path}
    ${content}=    Get File    ${screenshot_path}
    Should Contain    ${content}    Test screenshot data
    Remove File    ${screenshot_path}

Screenshot Metadata Test
    [Documentation]    Tests handling screenshot metadata
    ${timestamp}=    Evaluate    int(__import__('time').time())
    ${screenshot_name}=    Set Variable    screenshot_${timestamp}
    Should Not Be Empty    ${screenshot_name}
    Should Contain    ${screenshot_name}    screenshot_
