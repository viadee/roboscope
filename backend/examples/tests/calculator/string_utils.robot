*** Settings ***
Documentation    Tests for string manipulation operations.
Library          String
Library          Collections

*** Variables ***
${GREETING}      Hello, World!
${SEPARATOR}     -

*** Test Cases ***
Convert String Case
    [Documentation]    Verify upper/lower case conversion.
    [Tags]    smoke    string
    ${upper}=    Convert To Upper Case    ${GREETING}
    Should Be Equal    ${upper}    HELLO, WORLD!
    ${lower}=    Convert To Lower Case    ${GREETING}
    Should Be Equal    ${lower}    hello, world!

String Length
    [Documentation]    Verify string length measurement.
    [Tags]    string
    ${length}=    Get Length    ${GREETING}
    Should Be Equal As Numbers    ${length}    13

String Contains And Should Match
    [Documentation]    Verify substring checks and pattern matching.
    [Tags]    string
    Should Contain    ${GREETING}    World
    Should Not Contain    ${GREETING}    Goodbye
    Should Match Regexp    ${GREETING}    ^Hello.*!$

Split And Join Strings
    [Documentation]    Verify splitting a string and joining it back.
    [Tags]    string
    ${parts}=    Split String    one-two-three    ${SEPARATOR}
    Length Should Be    ${parts}    3
    Should Be Equal    ${parts}[0]    one
    Should Be Equal    ${parts}[1]    two
    Should Be Equal    ${parts}[2]    three
    ${joined}=    Catenate    SEPARATOR=${SEPARATOR}    one    two    three
    Should Be Equal    ${joined}    one-two-three

Strip And Trim Whitespace
    [Documentation]    Verify whitespace removal from strings.
    [Tags]    string
    ${padded}=    Set Variable    ${SPACE}${SPACE}hello${SPACE}${SPACE}
    ${stripped}=    Strip String    ${padded}
    Should Be Equal    ${stripped}    hello

Replace Substrings
    [Documentation]    Verify substring replacement.
    [Tags]    string
    ${result}=    Replace String    Hello, World!    World    Robot Framework
    Should Be Equal    ${result}    Hello, Robot Framework!
    ${result2}=    Replace String    aabbaabb    bb    cc
    Should Be Equal    ${result2}    aaccaacc

Fetch From Left And Right
    [Documentation]    Verify extracting parts of strings.
    [Tags]    string
    ${left}=    Fetch From Left    user@example.com    @
    Should Be Equal    ${left}    user
    ${right}=    Fetch From Right    user@example.com    @
    Should Be Equal    ${right}    example.com

Generate Random String
    [Documentation]    Verify random string generation.
    [Tags]    string
    ${random}=    Generate Random String    8    [LETTERS]
    ${length}=    Get Length    ${random}
    Should Be Equal As Numbers    ${length}    8

String Conversion And Formatting
    [Documentation]    Verify number-to-string conversion and formatting.
    [Tags]    string
    ${num_str}=    Convert To String    42
    Should Be Equal    ${num_str}    42
    ${formatted}=    Catenate    Result:    ${num_str}    points
    Should Be Equal    ${formatted}    Result: 42 points

Build Multiline String With Keywords
    [Documentation]    Verify building strings across multiple steps.
    [Tags]    string
    ${line1}=    Set Variable    Line one
    ${line2}=    Set Variable    Line two
    ${line3}=    Set Variable    Line three
    ${result}=    Catenate    SEPARATOR=\n    ${line1}    ${line2}    ${line3}
    Should Contain    ${result}    Line one
    Should Contain    ${result}    Line three
    @{lines}=    Split String    ${result}    \n
    Length Should Be    ${lines}    3
