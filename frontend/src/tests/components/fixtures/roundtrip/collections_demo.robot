*** Settings ***
Documentation    Tests for list and dictionary operations.
Library          Collections
Library          String

*** Test Cases ***
Create And Inspect List
    [Documentation]    Verify list creation and basic inspection.
    [Tags]    smoke    collections
    @{colors}=    Create List    red    green    blue    yellow
    Length Should Be    ${colors}    4
    Should Be Equal    ${colors}[0]    red
    Should Be Equal    ${colors}[-1]    yellow
    List Should Contain Value    ${colors}    green

Append And Remove List Items
    [Documentation]    Verify adding and removing items from a list.
    [Tags]    collections
    @{items}=    Create List    apple    banana
    Append To List    ${items}    cherry
    Length Should Be    ${items}    3
    Should Be Equal    ${items}[2]    cherry
    Remove From List    ${items}    0
    Length Should Be    ${items}    2
    Should Be Equal    ${items}[0]    banana

Sort A List
    [Documentation]    Verify sorting a list of strings alphabetically.
    [Tags]    collections
    @{unsorted}=    Create List    cherry    apple    banana    date
    Sort List    ${unsorted}
    Should Be Equal    ${unsorted}[0]    apple
    Should Be Equal    ${unsorted}[1]    banana
    Should Be Equal    ${unsorted}[2]    cherry
    Should Be Equal    ${unsorted}[3]    date

List Deduplication
    [Documentation]    Verify removing duplicates from a list.
    [Tags]    collections
    @{dupes}=    Create List    a    b    a    c    b    c    d
    ${unique}=    Remove Duplicates    ${dupes}
    Length Should Be    ${unique}    4
    List Should Contain Value    ${unique}    a
    List Should Contain Value    ${unique}    d

Create And Inspect Dictionary
    [Documentation]    Verify dictionary creation and key/value access.
    [Tags]    smoke    collections
    &{user}=    Create Dictionary    name=Alice    age=30    role=admin
    Should Be Equal    ${user}[name]    Alice
    Should Be Equal    ${user}[role]    admin
    Dictionary Should Contain Key    ${user}    age
    ${keys}=    Get Dictionary Keys    ${user}
    Length Should Be    ${keys}    3

Update Dictionary Values
    [Documentation]    Verify updating and adding dictionary entries.
    [Tags]    collections
    &{config}=    Create Dictionary    host=localhost    port=8080
    Set To Dictionary    ${config}    port=9090    debug=true
    Should Be Equal    ${config}[port]    9090
    Should Be Equal    ${config}[debug]    true
    Dictionary Should Contain Key    ${config}    host

Merge Two Dictionaries
    [Documentation]    Verify merging two dictionaries into one.
    [Tags]    collections
    &{defaults}=    Create Dictionary    color=blue    size=medium    theme=light
    &{overrides}=    Create Dictionary    size=large    theme=dark
    ${merged}=    Copy Dictionary    ${defaults}
    Set To Dictionary    ${merged}    size=${overrides}[size]    theme=${overrides}[theme]
    Should Be Equal    ${merged}[color]    blue
    Should Be Equal    ${merged}[size]    large
    Should Be Equal    ${merged}[theme]    dark

Filter List By Condition
    [Documentation]    Verify filtering a list using a custom keyword.
    [Tags]    collections
    @{numbers}=    Create List    ${1}    ${5}    ${12}    ${3}    ${8}    ${20}
    @{big}=    Filter Numbers Greater Than    ${numbers}    ${7}
    Length Should Be    ${big}    3
    List Should Contain Value    ${big}    ${12}
    List Should Contain Value    ${big}    ${8}
    List Should Contain Value    ${big}    ${20}

Nested Data Structures
    [Documentation]    Verify working with lists inside dictionaries.
    [Tags]    collections
    @{tags}=    Create List    python    testing    automation
    &{project}=    Create Dictionary    name=RoboScope    version=1.0
    Set To Dictionary    ${project}    tags=${tags}
    ${project_tags}=    Get From Dictionary    ${project}    tags
    Length Should Be    ${project_tags}    3
    List Should Contain Value    ${project_tags}    testing

Count Occurrences In List
    [Documentation]    Verify counting how many times a value appears.
    [Tags]    collections
    @{grades}=    Create List    A    B    A    C    A    B    A
    ${count_a}=    Count Values In List    ${grades}    A
    Should Be Equal As Numbers    ${count_a}    4
    ${count_b}=    Count Values In List    ${grades}    B
    Should Be Equal As Numbers    ${count_b}    2

*** Keywords ***
Filter Numbers Greater Than
    [Documentation]    Returns a new list containing only numbers greater than the threshold.
    [Arguments]    ${numbers}    ${threshold}
    @{result}=    Create List
    FOR    ${num}    IN    @{numbers}
        IF    ${num} > ${threshold}
            Append To List    ${result}    ${num}
        END
    END
    RETURN    @{result}
