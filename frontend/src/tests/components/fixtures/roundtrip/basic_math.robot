*** Settings ***
Documentation    Tests for basic arithmetic operations.
Library          String
Library          Collections

*** Variables ***
${PI}            3.14159
${MAX_INT}       ${9999}

*** Test Cases ***
Addition Of Positive Numbers
    [Documentation]    Verify that addition works for positive integers.
    [Tags]    smoke    arithmetic
    ${result}=    Evaluate    3 + 7
    Should Be Equal As Numbers    ${result}    10

Addition With Negative Numbers
    [Documentation]    Verify addition with negative operands.
    [Tags]    arithmetic
    ${result}=    Evaluate    -5 + 3
    Should Be Equal As Numbers    ${result}    -2
    ${result2}=    Evaluate    -10 + (-20)
    Should Be Equal As Numbers    ${result2}    -30

Subtraction
    [Documentation]    Verify subtraction of integers.
    [Tags]    arithmetic
    ${result}=    Evaluate    100 - 42
    Should Be Equal As Numbers    ${result}    58

Multiplication And Division
    [Documentation]    Verify multiplication and division.
    [Tags]    arithmetic
    ${product}=    Evaluate    6 * 7
    Should Be Equal As Numbers    ${product}    42
    ${quotient}=    Evaluate    84 / 4
    Should Be Equal As Numbers    ${quotient}    21

Integer Division And Modulo
    [Documentation]    Verify floor division and modulo operator.
    [Tags]    arithmetic
    ${floor}=    Evaluate    17 // 5
    Should Be Equal As Numbers    ${floor}    3
    ${mod}=    Evaluate    17 % 5
    Should Be Equal As Numbers    ${mod}    2

Floating Point Arithmetic
    [Documentation]    Verify floating point calculations using PI.
    [Tags]    arithmetic    float
    ${circumference}=    Evaluate    2 * ${PI} * 5
    Should Be True    abs(${circumference} - 31.4159) < 0.001
    ${area}=    Evaluate    ${PI} * 10**2
    Should Be True    abs(${area} - 314.159) < 0.001

Power And Square Root
    [Documentation]    Verify exponentiation and square root.
    [Tags]    arithmetic
    ${power}=    Evaluate    2 ** 10
    Should Be Equal As Numbers    ${power}    1024
    ${sqrt}=    Evaluate    144 ** 0.5
    Should Be Equal As Numbers    ${sqrt}    12

Comparison Operators
    [Documentation]    Verify comparison expressions evaluate correctly.
    [Tags]    smoke    logic
    Should Be True    10 > 5
    Should Be True    3 <= 3
    Should Be True    7 != 8
    Should Be True    ${MAX_INT} == 9999

Chained Calculations
    [Documentation]    Verify a multi-step calculation pipeline.
    [Tags]    arithmetic
    ${step1}=    Evaluate    10 + 20
    ${step2}=    Evaluate    ${step1} * 3
    ${step3}=    Evaluate    ${step2} - 10
    ${step4}=    Evaluate    ${step3} / 8
    Should Be Equal As Numbers    ${step4}    10

Absolute Value And Rounding
    [Documentation]    Verify abs() and round() built-in functions.
    [Tags]    arithmetic
    ${abs_val}=    Evaluate    abs(-42)
    Should Be Equal As Numbers    ${abs_val}    42
    ${rounded}=    Evaluate    round(3.14159, 2)
    Should Be Equal As Numbers    ${rounded}    3.14
