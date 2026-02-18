*** Settings ***
Documentation     Beispiel-Testfälle für Robot Framework
Library           String
Library           Collections

*** Variables ***
${GREETING}       Hallo Welt
${NUMBER}         42

*** Test Cases ***
Einfacher Test mit Assertions
    [Documentation]    Ein einfacher Test, der grundlegende Assertions demonstriert
    Should Be Equal As Strings    ${GREETING}    Hallo Welt
    Should Be Equal As Numbers    ${NUMBER}      42
    Should Be True    ${NUMBER} > 0

String-Operationen Test
    [Documentation]    Test für verschiedene String-Operationen
    ${result}=    Convert To Upper Case    ${GREETING}
    Should Be Equal    ${result}    HALLO WELT

    ${length}=    Get Length    ${GREETING}
    Should Be Equal As Numbers    ${length}    10

    Should Contain    ${GREETING}    Welt

Mathematische Operationen Test
    [Documentation]    Test für grundlegende mathematische Operationen
    ${sum}=    Evaluate    ${NUMBER} + 8
    Should Be Equal As Numbers    ${sum}    50

    ${product}=    Evaluate    ${NUMBER} * 2
    Should Be Equal As Numbers    ${product}    84

    ${division}=    Evaluate    ${NUMBER} / 6
    Should Be Equal As Numbers    ${division}    7

Listen-Operationen Test
    [Documentation]    Test für Operationen mit Listen
    @{fruits}=    Create List    Apfel    Banane    Orange
    ${count}=    Get Length    ${fruits}
    Should Be Equal As Numbers    ${count}    3

    List Should Contain Value    ${fruits}    Banane
    Should Be Equal    ${fruits}[0]    Apfel
