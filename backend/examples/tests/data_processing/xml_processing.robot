*** Settings ***
Documentation    Tests for XML document parsing and manipulation.
Library          XML
Library          Collections
Library          OperatingSystem

*** Variables ***
${BOOKS_XML}     SEPARATOR=\n
...    <?xml version="1.0" encoding="UTF-8"?>
...    <library>
...      <book id="1" genre="fiction">
...        <title>The Great Gatsby</title>
...        <author>F. Scott Fitzgerald</author>
...        <year>1925</year>
...        <price>12.99</price>
...      </book>
...      <book id="2" genre="science">
...        <title>A Brief History of Time</title>
...        <author>Stephen Hawking</author>
...        <year>1988</year>
...        <price>15.50</price>
...      </book>
...      <book id="3" genre="fiction">
...        <title>1984</title>
...        <author>George Orwell</author>
...        <year>1949</year>
...        <price>10.99</price>
...      </book>
...    </library>

*** Test Cases ***
Parse XML And Get Root Element
    [Documentation]    Verify parsing XML string and inspecting the root tag.
    [Tags]    smoke    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    ${tag}=    Evaluate    $xml.tag
    Should Be Equal    ${tag}    library

Get Single Element By XPath
    [Documentation]    Verify selecting a specific element via XPath.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    ${first_title}=    Get Element Text    ${xml}    .//book[@id='1']/title
    Should Be Equal    ${first_title}    The Great Gatsby

Get All Matching Elements
    [Documentation]    Verify finding all elements that match an XPath.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    @{books}=    Get Elements    ${xml}    .//book
    Length Should Be    ${books}    3

Read Element Attributes
    [Documentation]    Verify reading attributes from an XML element.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    ${genre}=    Get Element Attribute    ${xml}    genre    xpath=.//book[@id='2']
    Should Be Equal    ${genre}    science
    ${id}=    Get Element Attribute    ${xml}    id    xpath=.//book[@id='3']
    Should Be Equal    ${id}    3

Filter Elements By Attribute
    [Documentation]    Verify filtering books by genre attribute.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    @{fiction}=    Get Elements    ${xml}    .//book[@genre='fiction']
    Length Should Be    ${fiction}    2

Modify XML Element Text
    [Documentation]    Verify setting new text content on an element.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    Set Element Text    ${xml}    Updated Title    xpath=.//book[@id='1']/title
    ${new_title}=    Get Element Text    ${xml}    .//book[@id='1']/title
    Should Be Equal    ${new_title}    Updated Title

Add New Element To XML
    [Documentation]    Verify adding a child element to the XML tree.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    ${new_book}=    Parse Xml    <book id="4" genre="poetry"><title>Leaves of Grass</title><author>Walt Whitman</author><year>1855</year><price>9.99</price></book>
    Add Element    ${xml}    ${new_book}
    @{all_books}=    Get Elements    ${xml}    .//book
    Length Should Be    ${all_books}    4
    ${new_title}=    Get Element Text    ${xml}    .//book[@id='4']/title
    Should Be Equal    ${new_title}    Leaves of Grass

Remove Element From XML
    [Documentation]    Verify removing an element from the tree.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    Remove Element    ${xml}    xpath=.//book[@id='2']
    @{remaining}=    Get Elements    ${xml}    .//book
    Length Should Be    ${remaining}    2

Build XML Document From Scratch
    [Documentation]    Verify programmatically creating an XML document.
    [Tags]    xml
    ${root}=    Parse Xml    <config/>
    ${db}=    Parse Xml    <database host="localhost" port="5432"/>
    Add Element    ${root}    ${db}
    ${host}=    Get Element Attribute    ${root}    host    xpath=.//database
    Should Be Equal    ${host}    localhost

Extract All Text Values With XPath
    [Documentation]    Verify collecting all author names from the document.
    [Tags]    xml
    ${xml}=    Parse Xml    ${BOOKS_XML}
    @{authors}=    Get Elements Texts    ${xml}    .//author
    Length Should Be    ${authors}    3
    List Should Contain Value    ${authors}    George Orwell
