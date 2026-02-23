*** Settings ***
Documentation    Tests for JSON data handling and validation.
Library          JSONLibrary
Library          Collections
Library          OperatingSystem

Suite Setup      Create Temp JSON Directory
Suite Teardown   Remove Temp JSON Directory

*** Variables ***
${JSON_DIR}      ${TEMPDIR}/roboscope_json_tests
${USERS_JSON}    [{"id":1,"name":"Alice","role":"admin","active":true},{"id":2,"name":"Bob","role":"editor","active":true},{"id":3,"name":"Charlie","role":"viewer","active":false}]

*** Test Cases ***
Load JSON From String
    [Documentation]    Verify converting a JSON string into a Python object.
    [Tags]    smoke    json
    ${data}=    Convert String To Json    ${USERS_JSON}
    ${length}=    Get Length    ${data}
    Should Be Equal As Numbers    ${length}    3

Access JSON Object Fields
    [Documentation]    Verify reading fields from JSON objects using JSONPath.
    [Tags]    json
    ${data}=    Convert String To Json    ${USERS_JSON}
    ${names}=    Get Value From Json    ${data}    $[*].name
    Length Should Be    ${names}    3
    List Should Contain Value    ${names}    Alice
    List Should Contain Value    ${names}    Bob

Query JSON With JSONPath Filter
    [Documentation]    Verify filtering JSON data using JSONPath expressions.
    [Tags]    json
    ${data}=    Convert String To Json    ${USERS_JSON}
    ${admins}=    Get Value From Json    ${data}    $[?(@.role=='admin')].name
    Length Should Be    ${admins}    1
    Should Be Equal    ${admins}[0]    Alice

Get Nested JSON Values
    [Documentation]    Verify navigating nested JSON structures.
    [Tags]    json
    ${nested}=    Convert String To Json    {"server":{"host":"localhost","ports":[8000,8001,8002]}}
    ${host}=    Get Value From Json    ${nested}    $.server.host
    Should Be Equal    ${host}[0]    localhost
    ${ports}=    Get Value From Json    ${nested}    $.server.ports[*]
    Length Should Be    ${ports}    3

Update JSON Value
    [Documentation]    Verify modifying a value in a JSON structure.
    [Tags]    json
    ${data}=    Convert String To Json    {"name":"Alice","score":85}
    ${updated}=    Update Value To Json    ${data}    $.score    ${95}
    ${score}=    Get Value From Json    ${updated}    $.score
    Should Be Equal As Numbers    ${score}[0]    95

Add New Key To JSON Object
    [Documentation]    Verify adding a new key-value pair to JSON.
    [Tags]    json
    ${data}=    Convert String To Json    {"name":"Alice"}
    ${updated}=    Add Object To Json    ${data}    $.email    alice@example.com
    ${email}=    Get Value From Json    ${updated}    $.email
    Should Be Equal    ${email}[0]    alice@example.com

Delete Key From JSON
    [Documentation]    Verify removing a key from a JSON object.
    [Tags]    json
    ${data}=    Convert String To Json    {"a":1,"b":2,"c":3}
    ${updated}=    Delete Object From Json    ${data}    $.b
    ${keys}=    Get Value From Json    ${updated}    $
    Dictionary Should Not Contain Key    ${keys}[0]    b
    Dictionary Should Contain Key    ${keys}[0]    a

Save And Load JSON File
    [Documentation]    Verify writing JSON to a file and reading it back.
    [Tags]    json    file-io
    ${data}=    Convert String To Json    {"project":"RoboScope","version":"1.0"}
    ${path}=    Set Variable    ${JSON_DIR}/project.json
    Dump Json To File    ${path}    ${data}
    File Should Exist    ${path}
    ${loaded}=    Load Json From File    ${path}
    ${name}=    Get Value From Json    ${loaded}    $.project
    Should Be Equal    ${name}[0]    RoboScope

Validate JSON Against Schema
    [Documentation]    Verify that a JSON document conforms to a JSON Schema.
    [Tags]    json    validation
    ${schema_str}=    Set Variable    {"type":"object","required":["name","age"],"properties":{"name":{"type":"string"},"age":{"type":"integer","minimum":0}}}
    ${schema}=    Convert String To Json    ${schema_str}
    ${valid}=    Convert String To Json    {"name":"Alice","age":30}
    Validate Json By Schema    ${valid}    ${schema}

Validate JSON Schema Catches Invalid Data
    [Documentation]    Verify that schema validation rejects bad data.
    [Tags]    json    validation
    ${schema_str}=    Set Variable    {"type":"object","required":["name"],"properties":{"name":{"type":"string"}}}
    ${schema}=    Convert String To Json    ${schema_str}
    ${invalid}=    Convert String To Json    {"name":123}
    ${status}=    Run Keyword And Return Status    Validate Json By Schema    ${invalid}    ${schema}
    Should Be Equal    ${status}    ${FALSE}

*** Keywords ***
Create Temp JSON Directory
    [Documentation]    Creates a temp directory for JSON file tests.
    Create Directory    ${JSON_DIR}

Remove Temp JSON Directory
    [Documentation]    Cleans up the temp directory.
    Remove Directory    ${JSON_DIR}    recursive=True
