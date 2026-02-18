"""Mapping of well-known Robot Framework keywords to their source library.

Used to enrich keyword data from output.xml when the library attribute is missing.
"""

# BuiltIn library keywords
_BUILTIN = {
    "Call Method", "Catenate", "Comment", "Continue For Loop",
    "Continue For Loop If", "Convert To Binary", "Convert To Boolean",
    "Convert To Bytes", "Convert To Hex", "Convert To Integer",
    "Convert To Number", "Convert To Octal", "Convert To String",
    "Create Dictionary", "Create List", "Evaluate", "Exit For Loop",
    "Exit For Loop If", "Fail", "Fatal Error", "Get Count",
    "Get Length", "Get Library Instance", "Get Time", "Get Variable Value",
    "Get Variables", "Import Library", "Import Resource", "Import Variables",
    "Keyword Should Exist", "Length Should Be", "Log", "Log Many",
    "Log To Console", "Log Variables", "No Operation",
    "Pass Execution", "Pass Execution If", "Regexp Escape",
    "Reload Library", "Remove Tags", "Repeat Keyword",
    "Replace Variables", "Return From Keyword", "Return From Keyword If",
    "Run Keyword", "Run Keyword And Continue On Failure",
    "Run Keyword And Expect Error", "Run Keyword And Ignore Error",
    "Run Keyword And Return", "Run Keyword And Return If",
    "Run Keyword And Return Status", "Run Keyword And Warn On Failure",
    "Run Keyword If", "Run Keyword If All Tests Passed",
    "Run Keyword If Any Tests Failed", "Run Keyword If Test Failed",
    "Run Keyword If Test Passed", "Run Keyword If Timeout Occurred",
    "Run Keyword Unless", "Run Keywords",
    "Set Global Variable", "Set Library Search Order",
    "Set Log Level", "Set Suite Documentation", "Set Suite Metadata",
    "Set Suite Variable", "Set Tags", "Set Task Variable",
    "Set Test Documentation", "Set Test Message", "Set Test Variable",
    "Set Variable", "Set Variable If",
    "Should Be Empty", "Should Be Equal", "Should Be Equal As Integers",
    "Should Be Equal As Numbers", "Should Be Equal As Strings",
    "Should Be True", "Should Contain", "Should Contain Any",
    "Should Contain X Times", "Should End With", "Should Match",
    "Should Match Regexp", "Should Not Be Empty", "Should Not Be Equal",
    "Should Not Be Equal As Integers", "Should Not Be Equal As Numbers",
    "Should Not Be Equal As Strings", "Should Not Be True",
    "Should Not Contain", "Should Not Contain Any",
    "Should Not End With", "Should Not Match", "Should Not Match Regexp",
    "Should Not Start With", "Should Start With",
    "Skip", "Skip If", "Sleep",
    "Variable Should Exist", "Variable Should Not Exist",
    "Wait Until Keyword Succeeds",
    "Register Keyword To Run On Failure",
}

# Collections library keywords
_COLLECTIONS = {
    "Append To List", "Combine Lists", "Convert To Dictionary",
    "Convert To List", "Copy Dictionary", "Copy List",
    "Count Values In List", "Dictionaries Should Be Equal",
    "Dictionary Should Contain Item", "Dictionary Should Contain Key",
    "Dictionary Should Contain Sub Dictionary",
    "Dictionary Should Contain Value", "Dictionary Should Not Contain Key",
    "Dictionary Should Not Contain Value",
    "Get Dictionary Items", "Get Dictionary Keys", "Get Dictionary Values",
    "Get From Dictionary", "Get From List", "Get Match Count",
    "Get Matches", "Get Slice From List",
    "Insert Into List", "Keep In Dictionary",
    "List Should Contain Sub List", "List Should Contain Value",
    "List Should Not Contain Duplicates", "List Should Not Contain Value",
    "Lists Should Be Equal", "Log Dictionary", "Log List",
    "Pop From Dictionary", "Remove Duplicates", "Remove From Dictionary",
    "Remove From List", "Remove Values From List", "Reverse List",
    "Set List Value", "Set To Dictionary",
    "Should Contain Match", "Should Not Contain Match",
    "Sort List",
}

# String library keywords
_STRING = {
    "Convert To Lower Case", "Convert To Lowercase",
    "Convert To Upper Case", "Convert To Uppercase",
    "Decode Bytes To String", "Encode String To Bytes",
    "Fetch From Left", "Fetch From Right", "Format String",
    "Generate Random String", "Get Line", "Get Line Count",
    "Get Lines Containing String", "Get Lines Matching Pattern",
    "Get Lines Matching Regexp", "Get Regexp Matches",
    "Get String Length", "Get Substring",
    "Remove String", "Remove String Using Regexp",
    "Replace String", "Replace String Using Regexp",
    "Should Be Byte String", "Should Be Lower Case", "Should Be Lowercase",
    "Should Be String", "Should Be Title Case", "Should Be Titlecase",
    "Should Be Unicode String", "Should Be Upper Case", "Should Be Uppercase",
    "Should Not Be String",
    "Split String", "Split String From Right",
    "Split String To Characters", "Split To Lines", "Strip String",
}

# OperatingSystem library keywords
_OPERATING_SYSTEM = {
    "Append To Environment Variable", "Append To File",
    "Copy Directory", "Copy File", "Copy Files",
    "Count Directories In Directory", "Count Files In Directory",
    "Count Items In Directory", "Create Binary File", "Create Directory",
    "Create File", "Directory Should Be Empty",
    "Directory Should Exist", "Directory Should Not Be Empty",
    "Directory Should Not Exist",
    "Environment Variable Should Be Set",
    "Environment Variable Should Not Be Set",
    "File Should Be Empty", "File Should Exist",
    "File Should Not Be Empty", "File Should Not Exist",
    "Get Binary File", "Get Environment Variable",
    "Get Environment Variables", "Get File", "Get File Size",
    "Get Modified Time", "Grep File",
    "Join Path", "Join Paths",
    "List Directories In Directory", "List Directory",
    "List Files In Directory",
    "Log Environment Variables", "Log File",
    "Move Directory", "Move File", "Move Files",
    "Normalize Path",
    "Remove Directory", "Remove Environment Variable",
    "Remove File", "Remove Files",
    "Run", "Run And Return Rc", "Run And Return Rc And Output",
    "Set Environment Variable", "Set Modified Time",
    "Split Extension", "Split Path", "Touch",
    "Wait Until Created", "Wait Until Removed",
}

# DateTime library keywords
_DATETIME = {
    "Add Time To Date", "Add Time To Time",
    "Convert Date", "Convert Time",
    "Get Current Date", "Subtract Date From Date",
    "Subtract Time From Date", "Subtract Time From Time",
}

# Process library keywords
_PROCESS = {
    "Get Process Id", "Get Process Object", "Get Process Result",
    "Is Process Running", "Join Command Line",
    "Process Should Be Running", "Process Should Be Stopped",
    "Run Process", "Send Signal To Process", "Split Command Line",
    "Start Process", "Switch Process",
    "Terminate All Processes", "Terminate Process",
    "Wait For Process",
}

# XML library keywords
_XML = {
    "Add Element", "Clear Element", "Copy Element",
    "Element Attribute Should Be", "Element Attribute Should Match",
    "Element Should Exist", "Element Should Not Exist",
    "Element Should Not Have Attribute",
    "Element Text Should Be", "Element Text Should Match",
    "Element To String", "Elements Should Be Equal",
    "Elements Should Match", "Evaluate Xpath",
    "Get Child Elements", "Get Element", "Get Element Attribute",
    "Get Element Attributes", "Get Element Count", "Get Element Text",
    "Get Elements", "Get Elements Texts",
    "Log Element", "Parse Xml",
    "Remove Element", "Remove Element Attribute",
    "Remove Element Attributes", "Remove Elements",
    "Save Xml", "Set Element Attribute", "Set Element Tag",
    "Set Element Text",
}

# SeleniumLibrary keywords
_SELENIUM = {
    "Add Cookie", "Alert Should Be Present", "Alert Should Not Be Present",
    "Assign Id To Element",
    "Capture Element Screenshot", "Capture Page Screenshot",
    "Checkbox Should Be Selected", "Checkbox Should Not Be Selected",
    "Choose File", "Clear Element Text", "Click Button",
    "Click Element", "Click Element At Coordinates", "Click Image",
    "Click Link", "Close All Browsers", "Close Browser", "Close Window",
    "Cover Element", "Create Webdriver",
    "Current Frame Should Contain", "Current Frame Should Not Contain",
    "Delete All Cookies", "Delete Cookie",
    "Drag And Drop", "Drag And Drop By Offset",
    "Element Attribute Value Should Be", "Element Should Be Disabled",
    "Element Should Be Enabled", "Element Should Be Focused",
    "Element Should Be Visible", "Element Should Contain",
    "Element Should Not Be Visible", "Element Should Not Contain",
    "Element Text Should Be", "Element Text Should Not Be",
    "Execute Async Javascript", "Execute Javascript",
    "Frame Should Contain",
    "Get All Links", "Get Browser Aliases", "Get Browser Ids",
    "Get Cookie", "Get Cookies", "Get Element Attribute",
    "Get Element Count", "Get Element Size",
    "Get Horizontal Position", "Get List Items",
    "Get Location", "Get Locations",
    "Get Selected List Label", "Get Selected List Labels",
    "Get Selected List Value", "Get Selected List Values",
    "Get Selenium Implicit Wait", "Get Selenium Speed",
    "Get Selenium Timeout", "Get Session Id", "Get Source",
    "Get Table Cell", "Get Text", "Get Title", "Get Value",
    "Get Vertical Position", "Get WebElement", "Get WebElements",
    "Get Window Handles", "Get Window Ids", "Get Window Names",
    "Get Window Position", "Get Window Size", "Get Window Titles",
    "Go Back", "Go To",
    "Handle Alert",
    "Input Password", "Input Text", "Input Text Into Alert",
    "List Selection Should Be", "List Should Have No Selections",
    "Location Should Be", "Location Should Contain",
    "Log Location", "Log Source", "Log Title",
    "Maximize Browser Window", "Mouse Down", "Mouse Down On Image",
    "Mouse Down On Link", "Mouse Out", "Mouse Over", "Mouse Up",
    "Open Browser", "Open Context Menu",
    "Page Should Contain", "Page Should Contain Button",
    "Page Should Contain Checkbox", "Page Should Contain Element",
    "Page Should Contain Image", "Page Should Contain Link",
    "Page Should Contain List", "Page Should Contain Radio Button",
    "Page Should Contain Textfield",
    "Page Should Not Contain", "Page Should Not Contain Button",
    "Page Should Not Contain Checkbox", "Page Should Not Contain Element",
    "Page Should Not Contain Image", "Page Should Not Contain Link",
    "Page Should Not Contain List", "Page Should Not Contain Radio Button",
    "Page Should Not Contain Textfield",
    "Press Key", "Press Keys",
    "Radio Button Should Be Set To", "Radio Button Should Not Be Selected",
    "Register Keyword To Run On Failure",
    "Reload Page",
    "Remove Location Strategy",
    "Scroll Element Into View",
    "Select All From List", "Select Checkbox",
    "Select Frame", "Select From List By Index",
    "Select From List By Label", "Select From List By Value",
    "Select Radio Button", "Select Window",
    "Set Browser Implicit Wait", "Set Focus To Element",
    "Set Screenshot Directory",
    "Set Selenium Implicit Wait", "Set Selenium Speed",
    "Set Selenium Timeout", "Set Window Position", "Set Window Size",
    "Simulate Event", "Submit Form", "Switch Browser", "Switch Window",
    "Table Cell Should Contain", "Table Column Should Contain",
    "Table Footer Should Contain", "Table Header Should Contain",
    "Table Row Should Contain", "Table Should Contain",
    "Textarea Should Contain", "Textarea Value Should Be",
    "Textfield Should Contain", "Textfield Value Should Be",
    "Title Should Be",
    "Unselect All From List", "Unselect Checkbox",
    "Unselect Frame", "Unselect From List By Index",
    "Unselect From List By Label", "Unselect From List By Value",
    "Wait For Condition",
    "Wait Until Element Contains",
    "Wait Until Element Does Not Contain",
    "Wait Until Element Is Enabled",
    "Wait Until Element Is Not Visible",
    "Wait Until Element Is Visible",
    "Wait Until Location Contains",
    "Wait Until Location Does Not Contain",
    "Wait Until Location Is",
    "Wait Until Page Contains",
    "Wait Until Page Contains Element",
    "Wait Until Page Does Not Contain",
    "Wait Until Page Does Not Contain Element",
}

# Browser (Playwright) library keywords
_BROWSER = {
    "Add Style Tag", "Check Checkbox",
    "Click", "Click With Options", "Close Browser", "Close Context",
    "Close Page",
    "Drag And Drop", "Drag And Drop By Coordinates",
    "Evaluate Javascript",
    "Fill Secret", "Fill Text", "Focus",
    "Get Attribute", "Get Attribute Names",
    "Get BoundingBox", "Get Browser Catalog",
    "Get Classes", "Get Client Size", "Get Cookies",
    "Get Device", "Get Element", "Get Element Count",
    "Get Element States", "Get Elements",
    "Get Page Source", "Get Property", "Get Scroll Position",
    "Get Scroll Size", "Get Select Options", "Get Selected Options",
    "Get Style", "Get Table Cell Element",
    "Get Table Row Index", "Get Text", "Get Title", "Get Url",
    "Get Viewport Size",
    "Go To", "Handle Future Dialogs",
    "Highlight Elements", "Hover",
    "Http",
    "Keyboard Input", "Keyboard Key",
    "Mouse Button", "Mouse Move", "Mouse Wheel",
    "New Browser", "New Context", "New Page", "New Persistent Context",
    "Promise To",
    "Record Selector", "Register Keyword To Run On Failure",
    "Reload", "Run Async Keywords",
    "Scroll By", "Scroll To", "Scroll To Element",
    "Select Options By",
    "Set Browser Timeout", "Set Geolocation",
    "Set Offline", "Set Retry Assertions For",
    "Set Selector Prefix", "Set Strict Mode",
    "Set Viewport Size", "Switch Browser", "Switch Context",
    "Switch Page",
    "Take Screenshot",
    "Type Secret", "Type Text",
    "Uncheck Checkbox",
    "Upload File By Selector",
    "Wait For", "Wait For All Promises",
    "Wait For Condition", "Wait For Download",
    "Wait For Elements State", "Wait For Function",
    "Wait For Load State", "Wait For Navigation",
    "Wait For Request", "Wait For Response",
    "Wait Until Network Is Idle",
}

# RequestsLibrary keywords
_REQUESTS = {
    "Create Client Cert Session", "Create Custom Session",
    "Create Digest Session", "Create Ntlm Session", "Create Session",
    "DELETE On Session", "Delete All Sessions",
    "GET On Session", "HEAD On Session",
    "OPTIONS On Session", "PATCH On Session",
    "POST On Session", "PUT On Session",
    "Session Exists", "Status Should Be",
    "Request Should Be Successful",
    "Update Session",
}

# DatabaseLibrary keywords
_DATABASE = {
    "Check If Exists In Database", "Check If Not Exists In Database",
    "Connect To Database", "Connect To Database Using Custom Params",
    "Delete All Rows From Table", "Disconnect From Database",
    "Execute Sql Script", "Execute Sql String",
    "Query", "Description", "Row Count",
    "Row Count Is 0", "Row Count Is Equal To X",
    "Row Count Is Greater Than X", "Row Count Is Less Than X",
    "Table Must Exist",
}

# SSHLibrary keywords
_SSH = {
    "Close All Connections", "Close Connection",
    "Directory Should Exist", "Directory Should Not Exist",
    "Enable Ssh Logging", "Execute Command",
    "File Should Exist", "File Should Not Exist",
    "Get Connection", "Get Connections", "Get Directory",
    "Get File", "Get Pre Login Banner",
    "List Directories In Directory", "List Directory",
    "List Files In Directory",
    "Login", "Login With Public Key",
    "Open Connection",
    "Put Directory", "Put File",
    "Read", "Read Command Output", "Read Until",
    "Read Until Prompt", "Read Until Regexp",
    "Set Client Configuration", "Set Default Configuration",
    "Start Command", "Switch Connection",
    "Write", "Write Bare", "Write Until Expected Output",
}


def _build_lookup() -> dict[str, str]:
    """Build a single flat lookup dict: keyword_name_lower -> library_name."""
    mapping: dict[str, str] = {}
    libs = {
        "BuiltIn": _BUILTIN,
        "Collections": _COLLECTIONS,
        "String": _STRING,
        "OperatingSystem": _OPERATING_SYSTEM,
        "DateTime": _DATETIME,
        "Process": _PROCESS,
        "XML": _XML,
        "SeleniumLibrary": _SELENIUM,
        "Browser": _BROWSER,
        "RequestsLibrary": _REQUESTS,
        "DatabaseLibrary": _DATABASE,
        "SSHLibrary": _SSH,
    }
    for lib_name, keywords in libs.items():
        for kw in keywords:
            lower = kw.lower()
            # First library to claim a keyword wins (BuiltIn takes priority)
            if lower not in mapping:
                mapping[lower] = lib_name
    return mapping


KEYWORD_TO_LIBRARY: dict[str, str] = _build_lookup()


def resolve_keyword_library(keyword_name: str) -> str:
    """Resolve a keyword name to its most likely library.

    Returns the library name if found in the mapping, or empty string if unknown.
    """
    return KEYWORD_TO_LIBRARY.get(keyword_name.lower(), "")
