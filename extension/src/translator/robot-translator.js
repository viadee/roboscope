const seleniumLibraryMap = {
  url: { keyword: 'Open Browser' },
  text: { keyword: 'Input Text', value: 'y' },
  file: { keyword: 'Choose File', value: 'y' },
  button: { keyword: 'Click Button' },
  a: { keyword: 'Click Link' },
  select: { keyword: 'Select From List By Value', value: 'y' },
  // radio:  { keyword: 'Select Radio Button', value: 'y' },
  demo: { keyword: 'Sleep    ${SLEEP}' },
  verify: { keyword: 'Wait Until Page Contains Element' },
  default: { keyword: 'Click Element' }
};

const rfbrowserMap = {
  url: { keyword: 'New Page' },
  text: { keyword: 'Fill Text', value: 'y' },
  // file: { keyword: 'Choose File', value: 'y' },
  button: { keyword: 'Click' },
  a: { keyword: 'Click' },
  // FIXME: select: { keyword: 'Select Options By  attribute=value', value: 'y' },
  // radio:  { keyword: 'Select Radio Button', value: 'y' },
  demo: { keyword: 'Sleep    ${SLEEP}' },
  verify: { keyword: 'Wait For Elements State' },
  default: { keyword: 'Click' }
};


/**
 * @param {'SeleniumLibrary' | 'Browser'} target
  * @param {'rpa' | 'testing'} syntax
 */
export const initializeTranslator = (target, syntax) => {
  const map = target === 'SeleniumLibrary'
    ? seleniumLibraryMap
    : rfbrowserMap;

  let syntaxWord;
  let cases;

  if (syntax === 'rpa') {
    syntaxWord = 'Task';
    cases = 'Tasks';
  } else {
    syntaxWord = 'Test';
    cases = 'Test Cases';
  }

  return {
    generateOutput(list, length, demo, verify) {
      const events = this._generateEvents(list, length, demo, verify);

      return events.join('\n');
    },

    generateFile(list, length, demo, verify) {
      let events = this._generateEvents(list, length, demo, verify);

      events = events.join('\n    ');

      return `*** Settings ***
Documentation     A Robot script with a single task for ${list[0].title}
...               Created by Robot recorder"
Library           ${target}    timeout=10
${syntaxWord} Teardown     Close Browser
*** Variables ***
\${BROWSER}    chromium
\${SLEEP}    3
\n*** ${cases} ***
${list[0].title} ${syntaxWord}
    ${events}`;
    },

    _generatePath(attr) {
      const type = map[attr.type] || map.default;
      let path = type.keyword;

      path += attr.type === 'url' ? `    ${attr.path}    \${BROWSER}` : `    ${attr.path}`;
      path += attr.value && type.value ? `    ${attr.value}` : '';

      return path;
    },

    _generateDemo(demo) {
      return demo ? map.demo.keyword : '';
    },

    _generateVerify(attr, verify) {
      return attr.path && verify ? `${map.verify.keyword}    ${attr.path}` : '';
    },

    _generateEvents(list, length, demo, verify) {
      let event = null;
      const events = [];
      for (let i = 0; i < list.length && i < length; i++) {
        if (i > 0) {
          event = this._generateVerify(list[i], verify);
          event && events.push(event);
        }
        event = this._generatePath(list[i]);
        event && events.push(event);
        event = this._generateDemo(demo);
        event && events.push(event);
      }
      return events;
    }
  };
};

if (typeof exports !== 'undefined') exports.initializeTranslator = initializeTranslator;
