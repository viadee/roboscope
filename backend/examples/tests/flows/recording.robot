*** Settings ***
Library           Browser

*** Test Cases ***
Recording 17
    Scroll To Element    text=de‪Deutsch‬‪English (United Kingdom)‬‪Español (España)‬‪Fra…
    Click    text=Alle ablehnen
    Click    role=combobox[name="Suche"]
    Press Keys    role=combobox[name="Suche"]    Enter
