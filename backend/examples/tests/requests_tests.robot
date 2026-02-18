*** Settings ***
Documentation     HTTP API tests using RequestsLibrary
Library           RequestsLibrary
Library           Collections

*** Variables ***
${BASE_URL}       https://httpbin.org

*** Test Cases ***
GET Request Test
    [Documentation]    Tests a simple GET request
    Create Session    httpbin    ${BASE_URL}
    ${response}=    GET On Session    httpbin    /get
    Should Be Equal As Numbers    ${response.status_code}    200
    Delete All Sessions

POST Request Test
    [Documentation]    Tests a POST request with JSON data
    Create Session    httpbin    ${BASE_URL}
    ${data}=    Create Dictionary    name=Robot    test=framework
    ${response}=    POST On Session    httpbin    /post    json=${data}
    Should Be Equal As Numbers    ${response.status_code}    200
    Delete All Sessions

Request with Custom Headers
    [Documentation]    Tests sending custom headers with request
    Create Session    httpbin    ${BASE_URL}
    ${headers}=    Create Dictionary    User-Agent=RobotFramework    X-Custom-Header=TestValue
    ${response}=    GET On Session    httpbin    /headers    headers=${headers}
    Should Be Equal As Numbers    ${response.status_code}    200
    Dictionary Should Contain Key    ${response.headers}    Content-Type
    Delete All Sessions
