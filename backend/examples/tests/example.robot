*** Settings ***
Documentation    Robot Framework Grundlegende Operationen Tests
...              Author: 
...              Created: 2025-01-30
Library    String
Library    Collections

*** Variables ***
${GREETING}    Hallo Welt
${NUMBER}      ${42}

*** Test Cases ***
Einfacher Test mit Assertions
    [Documentation]    Demonstriert grundlegende Assertions, indem geprüft wird, ob die Variable GREETING den Wert 'Hallo Welt' hat, die Variable NUMBER den Wert 42 hat und NUMBER größer als 0 ist
    Prüfe Ob Variable Als Zeichenkette Gleich Ist    ${GREETING}    Hallo Welt
    Prüfe Ob Variable Als Zahl Gleich Ist    ${NUMBER}    42
    Prüfe Ob Bedingung Wahr Ist    ${NUMBER} > 0

String-Operationen Test
    [Documentation]    Testet verschiedene String-Operationen auf der Variable GREETING, einschließlich Umwandlung in Großbuchstaben, Längenermittlung und Teilstring-Prüfung
    ${UPPER_GREETING}=    Wandle String In Großbuchstaben Um    ${GREETING}
    Prüfe Ob Variable Als Zeichenkette Gleich Ist    ${UPPER_GREETING}    HALLO WELT
    ${GREETING_LENGTH}=    Ermittle Länge Von Variable    ${GREETING}
    Prüfe Ob Länge Gleich Ist    ${GREETING_LENGTH}    10
    Prüfe Ob String Teilstring Enthält    ${GREETING}    Welt

Mathematische Operationen Test
    [Documentation]    Testet grundlegende mathematische Operationen (Addition, Multiplikation, Division) mit der Variable NUMBER (Wert 42)
    ${SUMME}=    Berechne Summe    ${NUMBER}    8
    Prüfe Ob Variable Als Zahl Gleich Ist    ${SUMME}    50
    ${PRODUKT}=    Berechne Produkt    ${NUMBER}    2
    Prüfe Ob Variable Als Zahl Gleich Ist    ${PRODUKT}    84
    ${QUOTIENT}=    Berechne Quotienten    ${NUMBER}    6
    Prüfe Ob Variable Als Zahl Gleich Ist    ${QUOTIENT}    7

Listen-Operationen Test
    [Documentation]    Testet Operationen auf einer Liste mit drei Früchten, einschließlich Längenprüfung, Enthaltensein eines Elements und Zugriff auf das erste Element
    ${FRUCHT_LISTE}=    Erstelle Liste Mit Elementen    Apfel    Banane    Orange
    ${LISTEN_LÄNGE}=    Ermittle Länge Von Variable    ${FRUCHT_LISTE}
    Prüfe Ob Länge Gleich Ist    ${LISTEN_LÄNGE}    3
    Prüfe Ob Liste Element Enthält    ${FRUCHT_LISTE}    Banane
    Prüfe Ob Erstes Element Gleich Ist    ${FRUCHT_LISTE}    Apfel

*** Keywords ***
Prüfe Ob Variable Als Zeichenkette Gleich Ist
    [Documentation]    Prüft, ob eine Variable als Zeichenkette einem erwarteten Wert entspricht
    [Arguments]    ${actual}    ${expected}
    Should Be Equal As Strings    ${actual}    ${expected}

Prüfe Ob Variable Als Zahl Gleich Ist
    [Documentation]    Prüft, ob eine Variable als Zahl einem erwarteten Wert entspricht
    [Arguments]    ${actual}    ${expected}
    Should Be Equal As Numbers    ${actual}    ${expected}

Prüfe Ob Bedingung Wahr Ist
    [Documentation]    Prüft, ob eine gegebene Bedingung wahr ist
    [Arguments]    ${condition}
    Should Be True    ${condition}

Wandle String In Großbuchstaben Um
    [Documentation]    Wandelt einen String in Großbuchstaben um und gibt das Ergebnis zurück
    [Arguments]    ${text}
    ${upper}=    Convert To Upper Case    ${text}
    [Return]    ${upper}

Ermittle Länge Von Variable
    [Documentation]    Ermittelt die Länge einer Variable (String oder Liste) und gibt sie zurück
    [Arguments]    ${variable}
    ${length}=    Get Length    ${variable}
    [Return]    ${length}

Prüfe Ob Länge Gleich Ist
    [Documentation]    Prüft, ob eine ermittelte Länge einem erwarteten Wert entspricht
    [Arguments]    ${actual_length}    ${expected_length}
    Should Be Equal As Numbers    ${actual_length}    ${expected_length}

Prüfe Ob String Teilstring Enthält
    [Documentation]    Prüft, ob ein String einen bestimmten Teilstring enthält
    [Arguments]    ${text}    ${substring}
    Should Contain    ${text}    ${substring}

Berechne Summe
    [Documentation]    Berechnet die Summe zweier Zahlen und gibt das Ergebnis zurück
    [Arguments]    ${zahl1}    ${zahl2}
    ${ergebnis}=    Evaluate    ${zahl1} + ${zahl2}
    [Return]    ${ergebnis}

Berechne Produkt
    [Documentation]    Berechnet das Produkt zweier Zahlen und gibt das Ergebnis zurück
    [Arguments]    ${zahl1}    ${zahl2}
    ${ergebnis}=    Evaluate    ${zahl1} * ${zahl2}
    [Return]    ${ergebnis}

Berechne Quotienten
    [Documentation]    Berechnet den Quotienten zweier Zahlen und gibt das Ergebnis zurück
    [Arguments]    ${zahl1}    ${zahl2}
    ${ergebnis}=    Evaluate    ${zahl1} / ${zahl2}
    [Return]    ${ergebnis}

Erstelle Liste Mit Elementen
    [Documentation]    Erstellt eine Liste mit den angegebenen Elementen und gibt sie zurück
    [Arguments]    @{elemente}
    ${liste}=    Create List    @{elemente}
    [Return]    ${liste}

Prüfe Ob Liste Element Enthält
    [Documentation]    Prüft, ob eine Liste ein bestimmtes Element enthält
    [Arguments]    ${liste}    ${element}
    List Should Contain Value    ${liste}    ${element}

Prüfe Ob Erstes Element Gleich Ist
    [Documentation]    Prüft, ob das erste Element einer Liste einem erwarteten Wert entspricht
    [Arguments]    ${liste}    ${expected}
    ${erstes_element}=    Get From List    ${liste}    0
    Should Be Equal As Strings    ${erstes_element}    ${expected}