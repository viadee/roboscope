*** Settings ***
Documentation     Selenium tests using SeleniumLibrary
Library           SeleniumLibrary
Library           Collections

*** Test Cases ***
Test Selenium Library Import
    [Documentation]    Tests SeleniumLibrary is available and importable
    ${lib_instance}=    Get Library Instance    SeleniumLibrary
    Variable Should Exist    ${lib_instance}

Selenium Locator Strategy Test
    [Documentation]    Tests various locator strategies understanding
    ${locators}=    Create Dictionary    id=test-id    class=test-class    xpath=//div[@id='test']
    Dictionary Should Contain Key    ${locators}    id
    Dictionary Should Contain Key    ${locators}    class
    Dictionary Should Contain Key    ${locators}    xpath
    ${locator_count}=    Get Length    ${locators}
    Should Be Equal As Numbers    ${locator_count}    3

Test Selenium WebDriver Options
    [Documentation]    Tests creating WebDriver options without opening browser
    ${chrome_options}=    Evaluate    sys.modules['selenium.webdriver'].ChromeOptions()    sys
    ${result1}=    Evaluate    $chrome_options.add_argument('--headless=new')
    ${result2}=    Evaluate    $chrome_options.add_argument('--no-sandbox')
    ${result3}=    Evaluate    $chrome_options.add_argument('--disable-dev-shm-usage')
    ${args}=    Evaluate    $chrome_options.arguments
    Should Contain    ${args}    --headless=new
    Should Contain    ${args}    --no-sandbox
