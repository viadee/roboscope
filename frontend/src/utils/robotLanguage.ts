import { StreamLanguage } from '@codemirror/language'

// Comprehensive Robot Framework keyword set (based on npp-robot + RF5/RF7)
export const RF_BUILTINS = new Set([
  // BuiltIn library
  'call method', 'catenate', 'comment', 'continue for loop', 'continue for loop if',
  'convert to binary', 'convert to boolean', 'convert to bytes', 'convert to hex',
  'convert to integer', 'convert to number', 'convert to octal', 'convert to string',
  'create dictionary', 'create list', 'evaluate', 'exit for loop', 'exit for loop if',
  'fail', 'fatal error', 'get count', 'get length', 'get library instance',
  'get time', 'get variable value', 'get variables', 'import library', 'import resource',
  'import variables', 'keyword should exist', 'length should be', 'log', 'log many',
  'log to console', 'log variables', 'no operation', 'pass execution', 'pass execution if',
  'regexp escape', 'reload library', 'remove tags', 'repeat keyword', 'replace variables',
  'return from keyword', 'return from keyword if', 'run keyword', 'run keyword and continue on failure',
  'run keyword and expect error', 'run keyword and ignore error', 'run keyword and return',
  'run keyword and return if', 'run keyword and return status', 'run keyword if',
  'run keyword if all critical tests passed', 'run keyword if all tests passed',
  'run keyword if any critical tests failed', 'run keyword if any tests failed',
  'run keyword if test failed', 'run keyword if test passed',
  'run keyword if timeout occurred', 'run keyword unless', 'run keywords',
  'set global variable', 'set library search order', 'set log level',
  'set suite documentation', 'set suite metadata', 'set suite variable',
  'set tags', 'set test documentation', 'set test message', 'set test variable',
  'set variable', 'set variable if', 'should be empty', 'should be equal',
  'should be equal as integers', 'should be equal as numbers', 'should be equal as strings',
  'should be true', 'should contain', 'should contain x times', 'should end with',
  'should match', 'should match regexp', 'should not be empty', 'should not be equal',
  'should not be equal as integers', 'should not be equal as numbers',
  'should not be equal as strings', 'should not be true', 'should not contain',
  'should not end with', 'should not match', 'should not match regexp',
  'should not start with', 'should start with', 'sleep',
  'variable should exist', 'variable should not exist', 'wait until keyword succeeds',
  'skip', 'skip if',
  // String library
  'convert to lowercase', 'convert to uppercase', 'decode bytes to string',
  'encode string to bytes', 'fetch from left', 'fetch from right',
  'generate random string', 'get line', 'get line count',
  'get lines containing string', 'get lines matching pattern', 'get lines matching regexp',
  'get regexp matches', 'get substring', 'remove string', 'remove string using regexp',
  'replace string', 'replace string using regexp', 'should be byte string',
  'should be lowercase', 'should be string', 'should be titlecase',
  'should be unicode string', 'should be uppercase', 'should not be string',
  'split string', 'split string from right', 'split string to characters', 'split to lines',
  // Collections library
  'append to list', 'combine lists', 'convert to dictionary', 'convert to list',
  'copy dictionary', 'copy list', 'count values in list', 'dictionaries should be equal',
  'dictionary should contain item', 'dictionary should contain key',
  'dictionary should contain sub dictionary', 'dictionary should contain value',
  'dictionary should not contain key', 'dictionary should not contain value',
  'get dictionary items', 'get dictionary keys', 'get dictionary values',
  'get from dictionary', 'get from list', 'get index from list',
  'get match count', 'get matches', 'get slice from list', 'insert into list',
  'keep in dictionary', 'list should contain sub list', 'list should contain value',
  'list should not contain duplicates', 'list should not contain value',
  'lists should be equal', 'log dictionary', 'log list', 'pop from dictionary',
  'remove duplicates', 'remove from dictionary', 'remove from list',
  'remove values from list', 'reverse list', 'set list value', 'set to dictionary',
  'should contain match', 'should not contain match', 'sort list',
  // DateTime library
  'add time to date', 'add time to time', 'convert date', 'convert time',
  'get current date', 'subtract date from date', 'subtract time from date',
  'subtract time from time',
  // OperatingSystem library
  'append to environment variable', 'append to file', 'copy directory', 'copy file',
  'copy files', 'count directories in directory', 'count files in directory',
  'count items in directory', 'create binary file', 'create directory', 'create file',
  'directory should be empty', 'directory should exist', 'directory should not be empty',
  'directory should not exist', 'empty directory', 'environment variable should be set',
  'environment variable should not be set', 'file should be empty', 'file should exist',
  'file should not be empty', 'file should not exist', 'get binary file',
  'get environment variable', 'get environment variables', 'get file', 'get file size',
  'get modified time', 'grep file', 'join path', 'join paths',
  'list directories in directory', 'list directory', 'list files in directory',
  'log environment variables', 'log file', 'move directory', 'move file', 'move files',
  'normalize path', 'remove directory', 'remove environment variable', 'remove file',
  'remove files', 'run', 'run and return rc', 'run and return rc and output',
  'set environment variable', 'set modified time', 'should exist', 'should not exist',
  'split extension', 'split path', 'touch', 'wait until created', 'wait until removed',
  // Process library
  'get process id', 'get process object', 'get process result', 'is process running',
  'join command line', 'process should be running', 'process should be stopped',
  'run process', 'send signal to process', 'split command line', 'start process',
  'stop all processes', 'stop process', 'switch process', 'terminate all processes',
  'terminate process', 'wait for process',
  // Telnet library
  'close all connections', 'close connection', 'execute command', 'login',
  'open connection', 'read', 'read until', 'read until prompt', 'read until regexp',
  'set default log level', 'set encoding', 'set newline', 'set prompt',
  'set telnetlib log level', 'set timeout', 'switch connection', 'write',
  'write bare', 'write control character', 'write until expected output',
  // XML library
  'add element', 'clear element', 'copy element', 'element attribute should be',
  'element attribute should match', 'element should exist', 'element should not exist',
  'element should not have attribute', 'element text should be', 'element text should match',
  'element to string', 'elements should be equal', 'elements should match',
  'evaluate xpath', 'get child elements', 'get element', 'get element attribute',
  'get element attributes', 'get element count', 'get element text', 'get elements',
  'get elements texts', 'log element', 'parse xml', 'remove element',
  'remove element attribute', 'remove element attributes', 'remove elements',
  'remove elements attribute', 'remove elements attributes', 'save xml',
  'set element attribute', 'set element tag', 'set element text',
  'set elements attribute', 'set elements tag', 'set elements text',
  // Screenshot library
  'set screenshot directory', 'take screenshot', 'take screenshot without embedding',
  // Dialogs library
  'execute manual step', 'get selection from user', 'get value from user', 'pause execution',
])

export function robotLanguage() {
  return StreamLanguage.define({
    startState() {
      return { section: '' as string, isKeywordDef: false }
    },
    token(stream, state: { section: string; isKeywordDef: boolean }) {
      // Beginning of line
      if (stream.sol()) {
        state.isKeywordDef = false
        // Section headers: *** Settings ***, *** Test Cases ***, etc.
        if (stream.match(/^\*{3}\s*(Settings?|Variables?|Test Cases?|Tasks?|Keywords?|Comments?)\s*\*{0,3}/i)) {
          const m = stream.current().toLowerCase()
          if (m.includes('setting')) state.section = 'settings'
          else if (m.includes('variable')) state.section = 'variables'
          else if (m.includes('test') || m.includes('task')) state.section = 'testcases'
          else if (m.includes('keyword')) state.section = 'keywords'
          else state.section = 'comments'
          return 'heading'
        }
        // Comment section: everything is a comment
        if (state.section === 'comments') {
          stream.skipToEnd()
          return 'comment'
        }
        // Test case / keyword name definitions (not indented)
        if ((state.section === 'testcases' || state.section === 'keywords') && !stream.match(/^\s/, false)) {
          state.isKeywordDef = true
          stream.skipToEnd()
          return 'definition'
        }
      }

      // Comments
      if (stream.match(/^#.*/)) return 'comment'
      // Separator: two or more spaces
      if (stream.match(/^  +/)) return 'punctuation'
      // Variables ${}, @{}, %{}, &{} with nested support
      if (stream.match(/^[$@%&]\{/)) {
        let depth = 1
        while (depth > 0 && !stream.eol()) {
          const ch = stream.next()
          if (ch === '{') depth++
          else if (ch === '}') depth--
        }
        return 'variableName'
      }
      // Test/keyword setting tags: [Setup], [Tags], [Teardown], [Arguments], [Documentation], [Return], [Template], [Timeout]
      if (stream.match(/^\[(Setup|Tags|Teardown|Documentation|Arguments|Return|Template|Timeout)\]/i)) {
        return 'meta'
      }
      // Settings section keywords
      if (state.section === 'settings' && stream.match(/^(Library|Resource|Variables|Suite Setup|Suite Teardown|Test Setup|Test Teardown|Test Template|Test Timeout|Force Tags|Default Tags|Metadata)\b/i)) {
        return 'meta'
      }
      // Control flow (RF5+)
      if (stream.match(/^\b(FOR|END|IF|ELSE IF|ELSE|TRY|EXCEPT|FINALLY|WHILE|BREAK|CONTINUE|RETURN|IN|IN RANGE|IN ENUMERATE|IN ZIP)\b/)) {
        return 'keyword'
      }
      // BDD prefixes
      if (stream.match(/^\b(Given|When|Then|And|But)\b/i)) {
        return 'keyword'
      }
      // Built-in keywords: match word sequences (single-space separated, stops at double-space separators)
      if (stream.match(/^[A-Za-z]/, false)) {
        const remaining = stream.string.slice(stream.pos)
        const m = remaining.match(/^[A-Za-z][A-Za-z0-9]*(?: [A-Za-z][A-Za-z0-9]*)*/)
        if (m) {
          const cellText = m[0]
          const words = cellText.split(' ')
          // Greedy: try longest keyword match first
          for (let len = words.length; len >= 1; len--) {
            const candidate = words.slice(0, len).join(' ')
            if (RF_BUILTINS.has(candidate.toLowerCase())) {
              stream.pos += candidate.length
              return 'function'
            }
          }
          // Not a keyword — consume the first word
          stream.pos += words[0].length
          return null
        }
        stream.next()
        return null
      }
      // Strings (quoted)
      if (stream.match(/^"(?:[^"\\]|\\.)*"/)) return 'string'
      if (stream.match(/^'(?:[^'\\]|\\.)*'/)) return 'string'
      // Numbers
      if (stream.match(/^-?\d+(\.\d+)?/)) return 'number'
      // Named arguments (arg=value)
      if (stream.match(/^[a-zA-Z_]\w*(?==)/)) return 'attributeName'
      // Skip whitespace
      if (stream.eatSpace()) return null
      stream.next()
      return null
    },
  })
}
