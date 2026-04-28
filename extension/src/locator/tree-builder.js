// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 viadee Unternehmensberatung AG.
//
// Walks an element + every ancestor up to (but not including) the
// document, and emits a list of {tagName: [{attr: value}, ...]} entries
// — one per level — that the XPath builder consumes.
//
// The returned shape, walked example for `<body><div class="d">
// <span class="s" id="s1"></span></div></body>` with selectors
// ['className','id']:
//
//   [
//     { span: [ { className: ['s'] }, { id: 's1' } ] },
//     { div:  [ { className: ['d'] } ] },
//     { body: [] }
//   ]
//
// Implementation: clean-room rewrite (RECORDER-LICENSE).
//
/* global Node */

const builder = {
  // Index of `element` among same-tag siblings under its parent. Used
  // by callers that want a raw position when no other attribute
  // disambiguates. Returns 0 when the element is the only sibling of
  // its tag (no need for a positional [N] suffix). Returns the 1-based
  // ordinal otherwise.
  _getIndex(element) {
    const siblings = element.parentNode ? element.parentNode.childNodes : [];
    let totalSameTag = 0;
    let position = 0;
    let foundSelf = false;
    for (let i = 0; i < siblings.length; i++) {
      const s = siblings[i];
      if (s === element) foundSelf = true;
      if (s && s.nodeType === Node.ELEMENT_NODE && s.tagName === element.tagName) {
        totalSameTag++;
        if (!foundSelf) position++;
      }
    }
    if (totalSameTag <= 1) return 0;
    return position + 1;
  },

  // Pull every requested selector off `element` and return them as a
  // compact list (skipping selectors that the element doesn't carry).
  // Special selectors:
  //   - 'className' splits the class list on whitespace and ALWAYS
  //     emits an entry (even an empty array). The XPath layer's
  //     subpath helper guards against zero-length lists itself.
  //   - 'index' is reserved for sibling-index disambiguation; the XPath
  //     builder synthesises it on demand, so we always return 1 here
  //     (preserves the original public API surface).
  _buildAttributes(element, selectors) {
    const out = [];
    for (const sel of selectors) {
      if (sel === 'className') {
        const cls = (element.className || '').toString();
        const parts = cls.length > 0 ? cls.split(' ').filter(Boolean) : [];
        out.push({ className: parts });
        continue;
      }
      if (sel === 'index') {
        out.push({ index: 1 });
        continue;
      }
      // Plain HTML / ARIA attributes (id, name, for, href, title, …).
      const value = element.getAttribute ? element.getAttribute(sel) : null;
      if (value !== null && value !== undefined && value !== '') {
        out.push({ [sel]: value });
      }
    }
    return out;
  },

  // Iteratively climb the tree so deep DOMs don't blow the stack. The
  // accumulator-style `acc` parameter is preserved from the original
  // public API even though we no longer recurse.
  build(element, selectors, acc) {
    let cur = element;
    while (cur && cur.nodeType !== Node.DOCUMENT_NODE) {
      const tag = (cur.tagName || '').toLowerCase();
      const attrs = this._buildAttributes(cur, selectors);
      acc.push({ [tag]: attrs });
      cur = cur.parentNode;
    }
    return acc;
  },
};

if (typeof exports !== 'undefined') exports.builder = builder;
