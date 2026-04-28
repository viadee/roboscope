// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 viadee Unternehmensberatung AG.
//
// Maps a DOM element to one of RoboScope's recordable action types.
// Returns `{ type, value? }` when the element is recordable, `null`
// otherwise. Implementation: clean-room rewrite (RECORDER-LICENSE).

// Input subtypes that yield a `text` recording (the user's input is
// captured as a string the test will type back). `password` is masked
// with `***` so secrets never leak into the recording payload.
const TEXT_INPUT_TYPES = new Set([
  'email', 'tel', 'url', 'number', 'search', 'text',
  'date', 'datetime-local', 'week', 'month', 'color',
]);

// Input subtypes recorded as a button-style click (no value to capture).
const CLICK_INPUT_TYPES = new Set(['submit', 'image', 'range', 'reset']);

function classifier(element) {
  if (!element || !element.tagName) return null;
  const tag = element.tagName.toLowerCase();

  if (tag === 'input') {
    const subtype = element.type;
    if (subtype === 'password')  return { type: 'text', value: '***' };
    if (subtype === 'radio')     return { type: 'radio', value: element.value };
    if (subtype === 'checkbox')  return { type: 'checkbox', value: element.checked };
    if (subtype === 'file')      return { type: 'file', value: element.value };
    if (TEXT_INPUT_TYPES.has(subtype)) return { type: 'text', value: element.value };
    if (CLICK_INPUT_TYPES.has(subtype)) return { type: subtype };
    // `hidden`, custom unknown subtypes → not recordable.
    return null;
  }
  if (tag === 'textarea') return { type: 'text', value: element.value };
  if (tag === 'select')   return { type: 'select', value: element.value };
  if (tag === 'a')        return { type: 'a', value: element.href };
  return null;
}

if (typeof exports !== 'undefined') exports.classifier = classifier;
