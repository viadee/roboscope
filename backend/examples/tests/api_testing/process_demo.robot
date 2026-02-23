*** Settings ***
Documentation    Tests demonstrating the Process library for running subprocesses.
Library          Process
Library          OperatingSystem
Library          String
Library          Collections

*** Test Cases ***
Run Echo Command
    [Documentation]    Verify running a simple echo command and capturing output.
    [Tags]    smoke    process
    ${result}=    Run Process    echo    Hello from Robot Framework    shell=True
    Should Be Equal As Numbers    ${result.rc}    0
    Should Contain    ${result.stdout}    Hello from Robot Framework

Run Python One-Liner
    [Documentation]    Verify executing an inline Python expression.
    [Tags]    process
    ${result}=    Run Process    python3    -c    print(6 * 7)
    Should Be Equal As Numbers    ${result.rc}    0
    Should Be Equal As Strings    ${result.stdout.strip()}    42

Capture Standard Error
    [Documentation]    Verify capturing stderr from a subprocess.
    [Tags]    process
    ${result}=    Run Process    python3    -c    import sys; sys.stderr.write("warning\\n")
    Should Contain    ${result.stderr}    warning

Check Process Exit Code
    [Documentation]    Verify detecting a non-zero exit code.
    [Tags]    process
    ${result}=    Run Process    python3    -c    import sys; sys.exit(1)
    Should Be Equal As Numbers    ${result.rc}    1

Run Command With Environment Variable
    [Documentation]    Verify passing environment variables to a subprocess.
    [Tags]    process
    ${result}=    Run Process    python3    -c    import os; print(os.environ.get('MY_VAR', ''))
    ...    env:MY_VAR=RoboScope
    Should Be Equal As Strings    ${result.stdout.strip()}    RoboScope

Run Date Command
    [Documentation]    Verify running the date command and getting output.
    [Tags]    process
    ${result}=    Run Process    date    +%Y
    Should Be Equal As Numbers    ${result.rc}    0
    Should Match Regexp    ${result.stdout.strip()}    ^\\d{4}$

Run Process With Timeout
    [Documentation]    Verify that a fast process completes within timeout.
    [Tags]    process
    ${result}=    Run Process    python3    -c    print("done")    timeout=10s
    Should Be Equal As Numbers    ${result.rc}    0
    Should Be Equal As Strings    ${result.stdout.strip()}    done

Run Pwd And Verify Output
    [Documentation]    Verify running pwd and getting a valid directory path.
    [Tags]    process
    ${result}=    Run Process    pwd
    Should Be Equal As Numbers    ${result.rc}    0
    Should Match Regexp    ${result.stdout.strip()}    ^/

List Python Version
    [Documentation]    Verify getting the Python version string.
    [Tags]    process
    ${result}=    Run Process    python3    --version
    Should Be Equal As Numbers    ${result.rc}    0
    Should Match Regexp    ${result.stdout}${result.stderr}    Python 3\\.\\d+

Run Multiline Python Script
    [Documentation]    Verify running a multi-statement Python script.
    [Tags]    process
    ${script}=    Catenate    SEPARATOR=;
    ...    data = [1, 2, 3, 4, 5]
    ...    total = sum(data)
    ...    print(f"sum={total}, count={len(data)}")
    ${result}=    Run Process    python3    -c    ${script}
    Should Be Equal As Numbers    ${result.rc}    0
    Should Contain    ${result.stdout}    sum=15
    Should Contain    ${result.stdout}    count=5
