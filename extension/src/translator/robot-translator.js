// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 viadee Unternehmensberatung AG.
//
// Translates a captured event list into Robot Framework source — both
// raw test-step lines (`generateOutput`) and a complete `.robot` file
// with header + variables (`generateFile`). Targets two RF libraries:
//
//   - SeleniumLibrary: classic Open Browser / Input Text / Click X
//   - Browser (rfbrowser): New Page / Fill Text / Click
//
// Implementation: clean-room rewrite (RECORDER-LICENSE).

// Per-library keyword tables. Each row is keyed by RoboScope action
// type (the `type` field a classifier emits). `value: 'y'` means the
// keyword takes the captured value as a second positional argument.
const KEYWORD_MAPS = {
  SeleniumLibrary: {
    url:     { keyword: 'Open Browser' },
    text:    { keyword: 'Input Text', value: 'y' },
    file:    { keyword: 'Choose File', value: 'y' },
    button:  { keyword: 'Click Button' },
    a:       { keyword: 'Click Link' },
    select:  { keyword: 'Select From List By Value', value: 'y' },
    demo:    { keyword: 'Sleep    ${SLEEP}' },
    verify:  { keyword: 'Wait Until Page Contains Element' },
    default: { keyword: 'Click Element' },
  },
  Browser: {
    url:     { keyword: 'New Page' },
    text:    { keyword: 'Fill Text', value: 'y' },
    button:  { keyword: 'Click' },
    a:       { keyword: 'Click' },
    demo:    { keyword: 'Sleep    ${SLEEP}' },
    verify:  { keyword: 'Wait For Elements State' },
    default: { keyword: 'Click' },
  },
};

const SYNTAX = {
  rpa:     { word: 'Task', section: 'Tasks' },
  testing: { word: 'Test', section: 'Test Cases' },
};

function pickMap(target) {
  return KEYWORD_MAPS[target] || KEYWORD_MAPS.Browser;
}

function pickSyntax(syntax) {
  return SYNTAX[syntax] || SYNTAX.testing;
}

// Render the line for a single captured event. `url` events also carry
// the global `${BROWSER}` argument; everything else is `keyword<TAB>locator`
// optionally followed by `<TAB>value` when the keyword consumes one.
function renderEvent(map, attr) {
  const row = map[attr.type] || map.default;
  let line = row.keyword;
  if (attr.type === 'url') {
    line += `    ${attr.path}    \${BROWSER}`;
  } else {
    line += `    ${attr.path}`;
  }
  if (attr.value && row.value) {
    line += `    ${attr.value}`;
  }
  return line;
}

function renderVerify(map, attr) {
  return attr.path ? `${map.verify.keyword}    ${attr.path}` : '';
}

function renderDemo(map) {
  return map.demo.keyword;
}

/**
 * Build a translator bound to (target, syntax). The returned object
 * exposes `generateOutput` / `generateFile` plus the underscore-prefixed
 * helpers the existing extension consumers (background.js, actions-view.js)
 * call into directly.
 *
 * @param {'SeleniumLibrary' | 'Browser'} target
 * @param {'rpa' | 'testing'} syntax
 */
export const initializeTranslator = (target, syntax) => {
  const map = pickMap(target);
  const { word: syntaxWord, section: cases } = pickSyntax(syntax);

  const api = {
    _generatePath(attr) { return renderEvent(map, attr); },
    _generateVerify(attr, verify) { return verify ? renderVerify(map, attr) : ''; },
    _generateDemo(demo) { return demo ? renderDemo(map) : ''; },

    _generateEvents(list, length, demo, verify) {
      const out = [];
      const limit = Math.min(list.length, length);
      for (let i = 0; i < limit; i++) {
        if (i > 0) {
          const v = this._generateVerify(list[i], verify);
          if (v) out.push(v);
        }
        const path = this._generatePath(list[i]);
        if (path) out.push(path);
        const d = this._generateDemo(demo);
        if (d) out.push(d);
      }
      return out;
    },

    generateOutput(list, length, demo, verify) {
      return this._generateEvents(list, length, demo, verify).join('\n');
    },

    generateFile(list, length, demo, verify) {
      const body = this._generateEvents(list, length, demo, verify).join('\n    ');
      const title = list[0] && list[0].title ? list[0].title : 'Recording';
      return `*** Settings ***
Documentation     A Robot script with a single task for ${title}
...               Created by Robot recorder"
Library           ${target}    timeout=10
${syntaxWord} Teardown     Close Browser
*** Variables ***
\${BROWSER}    chromium
\${SLEEP}    3

*** ${cases} ***
${title} ${syntaxWord}
    ${body}`;
    },
  };

  return api;
};

if (typeof exports !== 'undefined') exports.initializeTranslator = initializeTranslator;
