*** Settings ***
Documentation    Tests using the FakerLibrary to generate and validate test data.
Library          FakerLibrary    locale=en_US
Library          String
Library          Collections

*** Test Cases ***
Generate Fake Name
    [Documentation]    Verify generating a random full name.
    [Tags]    smoke    faker
    ${name}=    FakerLibrary.Name
    Should Not Be Empty    ${name}
    Should Match Regexp    ${name}    ^[A-Za-z .'-]+$

Generate Fake Email
    [Documentation]    Verify generating a random email address.
    [Tags]    faker
    ${email}=    FakerLibrary.Email
    Should Not Be Empty    ${email}
    Should Contain    ${email}    @
    Should Match Regexp    ${email}    ^[^@]+@[^@]+\\.[^@]+$

Generate Fake Address Components
    [Documentation]    Verify generating address parts individually.
    [Tags]    faker
    ${city}=    FakerLibrary.City
    ${country}=    FakerLibrary.Country
    ${zipcode}=    FakerLibrary.Zipcode
    Should Not Be Empty    ${city}
    Should Not Be Empty    ${country}
    Should Not Be Empty    ${zipcode}

Generate Fake Phone Number
    [Documentation]    Verify generating a random phone number.
    [Tags]    faker
    ${phone}=    FakerLibrary.Phone Number
    Should Not Be Empty    ${phone}
    ${length}=    Get Length    ${phone}
    Should Be True    ${length} >= 7

Generate Random Integer In Range
    [Documentation]    Verify generating a random integer within bounds.
    [Tags]    faker
    ${num}=    FakerLibrary.Random Int    min=10    max=99
    Should Be True    ${num} >= 10
    Should Be True    ${num} <= 99

Generate Random Text Paragraph
    [Documentation]    Verify generating a paragraph of lorem ipsum text.
    [Tags]    faker
    ${text}=    FakerLibrary.Paragraph    nb_sentences=3
    Should Not Be Empty    ${text}
    ${length}=    Get Length    ${text}
    Should Be True    ${length} > 20

Generate Fake Date
    [Documentation]    Verify generating a random date string.
    [Tags]    faker
    ${date}=    FakerLibrary.Date
    Should Match Regexp    ${date}    ^\\d{4}-\\d{2}-\\d{2}$

Generate Unique Values
    [Documentation]    Verify that multiple generated emails are distinct.
    [Tags]    faker
    @{emails}=    Create List
    FOR    ${i}    IN RANGE    5
        ${email}=    FakerLibrary.Email
        Append To List    ${emails}    ${email}
    END
    ${unique}=    Remove Duplicates    ${emails}
    Length Should Be    ${unique}    5

Generate Fake Company Info
    [Documentation]    Verify generating company-related fake data.
    [Tags]    faker
    ${company}=    FakerLibrary.Company
    ${bs}=    FakerLibrary.Bs
    ${job}=    FakerLibrary.Job
    Should Not Be Empty    ${company}
    Should Not Be Empty    ${bs}
    Should Not Be Empty    ${job}

Generate Fake Boolean And UUID
    [Documentation]    Verify generating a random boolean and UUID.
    [Tags]    faker
    ${bool}=    FakerLibrary.Boolean
    Should Be True    '${bool}' in ['True', 'False']
    ${uuid}=    FakerLibrary.Uuid4
    Should Match Regexp    ${uuid}    ^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$
