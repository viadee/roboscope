*** Settings ***
Documentation    Tests for HTTP API interactions using RequestsLibrary.
...              Uses httpbin.org — a public HTTP testing service.
Library          RequestsLibrary
Library          Collections

Suite Setup      Create Session    httpbin    https://httpbin.org    verify=${True}
Suite Teardown   Delete All Sessions

*** Test Cases ***
GET Request Returns 200
    [Documentation]    Verify a simple GET request succeeds.
    [Tags]    smoke    http
    ${resp}=    GET On Session    httpbin    /get
    Should Be Equal As Numbers    ${resp.status_code}    200

GET Response Contains Headers
    [Documentation]    Verify the response includes standard headers.
    [Tags]    http
    ${resp}=    GET On Session    httpbin    /get
    Dictionary Should Contain Key    ${resp.headers}    Content-Type
    Should Contain    ${resp.headers}[Content-Type]    application/json

GET With Query Parameters
    [Documentation]    Verify query parameters are echoed back.
    [Tags]    http
    ${params}=    Create Dictionary    framework=robot    version=7
    ${resp}=    GET On Session    httpbin    /get    params=${params}
    Should Be Equal As Numbers    ${resp.status_code}    200
    ${json}=    Set Variable    ${resp.json()}
    Should Be Equal    ${json}[args][framework]    robot

POST Request With JSON Body
    [Documentation]    Verify sending JSON data via POST.
    [Tags]    http
    ${body}=    Create Dictionary    project=RoboScope    tests=${40}
    ${resp}=    POST On Session    httpbin    /post    json=${body}
    Should Be Equal As Numbers    ${resp.status_code}    200
    ${json}=    Set Variable    ${resp.json()}
    Should Be Equal    ${json}[json][project]    RoboScope

PUT Request
    [Documentation]    Verify a PUT request succeeds.
    [Tags]    http
    ${body}=    Create Dictionary    updated=true
    ${resp}=    PUT On Session    httpbin    /put    json=${body}
    Should Be Equal As Numbers    ${resp.status_code}    200

DELETE Request
    [Documentation]    Verify a DELETE request succeeds.
    [Tags]    http
    ${resp}=    DELETE On Session    httpbin    /delete
    Should Be Equal As Numbers    ${resp.status_code}    200

Custom Request Headers
    [Documentation]    Verify sending and receiving custom headers.
    [Tags]    http
    ${headers}=    Create Dictionary    X-Custom-Header=RoboScope-Test    Accept=application/json
    ${resp}=    GET On Session    httpbin    /headers    headers=${headers}
    ${json}=    Set Variable    ${resp.json()}
    Should Be Equal    ${json}[headers][X-Custom-Header]    RoboScope-Test

HTTP Status Code Handling
    [Documentation]    Verify handling specific HTTP status codes.
    [Tags]    http
    ${resp}=    GET On Session    httpbin    /status/200    expected_status=200
    Should Be Equal As Numbers    ${resp.status_code}    200
    ${resp404}=    GET On Session    httpbin    /status/404    expected_status=404
    Should Be Equal As Numbers    ${resp404.status_code}    404

Response Contains User-Agent
    [Documentation]    Verify the User-Agent header is sent automatically.
    [Tags]    http
    ${resp}=    GET On Session    httpbin    /user-agent
    ${json}=    Set Variable    ${resp.json()}
    Should Not Be Empty    ${json}[user-agent]

Base64 Decode Endpoint
    [Documentation]    Verify httpbin's base64 decode service.
    [Tags]    http
    ${resp}=    GET On Session    httpbin    /base64/Um9ib1Njb3Bl
    Should Be Equal As Strings    ${resp.text}    RoboScope
