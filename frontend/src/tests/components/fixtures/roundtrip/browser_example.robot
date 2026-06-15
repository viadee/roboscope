
*** Settings ***
Library    Browser

*** Test Cases ***
Beispiel 1
    New Page    https://example.cypress.io
    Click    "type"
    Get Url    *=    /commands/actions
    Type Text    .action-email    fake@email.com
    Get Text     .action-email    ==    fake@email.com
