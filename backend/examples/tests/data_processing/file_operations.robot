*** Settings ***
Documentation    Tests for file system and date/time operations.
Library          OperatingSystem
Library          String
Library          DateTime
Library          Collections

Suite Setup      Create Temp Work Directory
Suite Teardown   Remove Temp Work Directory

*** Variables ***
${WORK_DIR}      ${TEMPDIR}/roboscope_example_tests

*** Test Cases ***
Create And Read A Text File
    [Documentation]    Verify writing and reading a plain text file.
    [Tags]    smoke    file-io
    ${path}=    Set Variable    ${WORK_DIR}/hello.txt
    Create File    ${path}    Hello from Robot Framework!\nThis is line two.
    File Should Exist    ${path}
    ${content}=    Get File    ${path}
    Should Contain    ${content}    Hello from Robot Framework!
    Should Contain    ${content}    line two

Append To An Existing File
    [Documentation]    Verify appending content to a file.
    [Tags]    file-io
    ${path}=    Set Variable    ${WORK_DIR}/log.txt
    Create File    ${path}    Entry 1\n
    Append To File    ${path}    Entry 2\n
    Append To File    ${path}    Entry 3\n
    ${content}=    Get File    ${path}
    Should Contain    ${content}    Entry 1
    Should Contain    ${content}    Entry 2
    Should Contain    ${content}    Entry 3

Create Nested Directory Structure
    [Documentation]    Verify creating nested directories and files.
    [Tags]    file-io
    ${nested}=    Set Variable    ${WORK_DIR}/level1/level2/level3
    Create Directory    ${nested}
    Directory Should Exist    ${nested}
    Create File    ${nested}/deep_file.txt    Found me!
    File Should Exist    ${nested}/deep_file.txt

List Directory Contents
    [Documentation]    Verify listing files in a directory.
    [Tags]    file-io
    ${dir}=    Set Variable    ${WORK_DIR}/listing_test
    Create Directory    ${dir}
    Create File    ${dir}/alpha.txt    a
    Create File    ${dir}/beta.txt    b
    Create File    ${dir}/gamma.txt    c
    @{files}=    List Files In Directory    ${dir}
    Length Should Be    ${files}    3
    List Should Contain Value    ${files}    alpha.txt

Copy And Move Files
    [Documentation]    Verify copying and moving files between directories.
    [Tags]    file-io
    ${src}=    Set Variable    ${WORK_DIR}/source.txt
    Create File    ${src}    Original content
    Copy File    ${src}    ${WORK_DIR}/copied.txt
    File Should Exist    ${WORK_DIR}/copied.txt
    File Should Exist    ${src}
    Move File    ${WORK_DIR}/copied.txt    ${WORK_DIR}/moved.txt
    File Should Exist    ${WORK_DIR}/moved.txt
    File Should Not Exist    ${WORK_DIR}/copied.txt

Get And Verify File Size
    [Documentation]    Verify that file size is reported correctly.
    [Tags]    file-io
    ${path}=    Set Variable    ${WORK_DIR}/sized.txt
    Create File    ${path}    ABCDEFGHIJ
    ${size}=    Get File Size    ${path}
    Should Be Equal As Numbers    ${size}    10

Environment Variable Access
    [Documentation]    Verify reading an environment variable.
    [Tags]    smoke    env
    ${home}=    Get Environment Variable    HOME    default=/tmp
    Should Not Be Empty    ${home}

Get Current Date And Time
    [Documentation]    Verify retrieving and formatting the current timestamp.
    [Tags]    datetime
    ${now}=    Get Current Date    result_format=%Y-%m-%d
    Should Match Regexp    ${now}    ^\\d{4}-\\d{2}-\\d{2}$

Add And Subtract Time
    [Documentation]    Verify date arithmetic with the DateTime library.
    [Tags]    datetime
    ${base}=    Set Variable    2026-01-15 10:00:00
    ${plus_2h}=    Add Time To Date    ${base}    2 hours    result_format=%Y-%m-%d %H:%M:%S
    Should Be Equal    ${plus_2h}    2026-01-15 12:00:00
    ${minus_1d}=    Subtract Time From Date    ${base}    1 day    result_format=%Y-%m-%d %H:%M:%S
    Should Be Equal    ${minus_1d}    2026-01-14 10:00:00

Calculate Time Difference
    [Documentation]    Verify computing the difference between two timestamps.
    [Tags]    datetime
    ${start}=    Set Variable    2026-01-01 00:00:00
    ${end}=    Set Variable    2026-01-01 02:30:00
    ${diff}=    Subtract Date From Date    ${end}    ${start}
    Should Be Equal As Numbers    ${diff}    9000

*** Keywords ***
Create Temp Work Directory
    [Documentation]    Creates a clean temporary work directory for the suite.
    Create Directory    ${WORK_DIR}
    Directory Should Exist    ${WORK_DIR}

Remove Temp Work Directory
    [Documentation]    Cleans up the temporary work directory after all tests.
    Remove Directory    ${WORK_DIR}    recursive=True
