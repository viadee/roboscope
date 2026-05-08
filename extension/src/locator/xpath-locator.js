// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 viadee Unternehmensberatung AG.
//
// Synthesises an XPath locator from the leaf entry of a tree built by
// `builder.build()`. Picks the highest-priority attribute available
// (for > class > title > href > name > id > index) and disambiguates
// non-unique paths with `xpath=(…)[N]` after counting matches in the
// live DOM via `document.evaluate`.
//
// Implementation: clean-room rewrite (RECORDER-LICENSE).
//
/* global document XPathResult */

const SUBPATH_PRIORITY = ['for', 'class', 'title', 'href', 'name', 'id'];

const locator = {
  build(tree, element, type) {
    if (!tree || tree.length === 0) return '';
    const leaf = tree[0];
    const tag = Object.keys(leaf)[0];
    const attrs = leaf[tag] || [];

    // Pick the FIRST attribute the leaf carries that yields a non-empty
    // subpath. `attrs` is already in caller-supplied selector order, so
    // a higher-priority attribute earlier in the list wins.
    let path = '';
    for (const a of attrs) {
      const sub = this._getSubpath('', a, tag);
      if (sub) { path = sub; break; }
    }
    // Total path is `/` + the subpath (which itself starts with `/`)
    // → `//tag[@id="…"]` or just `//tag` for index-only.
    const fullPath = `/${path}`;

    if (!element) return fullPath;
    if (this._found(['@id', '@for'], fullPath)) return fullPath;
    if (this._found(['@name'], fullPath) && this._found(['select'], type)) return fullPath;

    const { count, index } = this._getIndex(fullPath, element);
    if (count > 1 && index > 1) return `xpath=(${fullPath})[${index}]`;
    return fullPath;
  },

  _found(needles, haystack) {
    for (const n of needles) {
      if (haystack.indexOf(n) !== -1) return true;
    }
    return false;
  },

  // Count nodes the path resolves against under document.body and
  // surface (count, index-of-element). `count==1, index==1` means the
  // path is unique; `count>1, index>1` means we need an `(…)[index]`
  // disambiguator.
  _getIndex(path, element) {
    let count = 1;
    let index = 1;
    const result = document.evaluate(
      `.${path}`,
      document.body,
      null,
      XPathResult.ORDERED_NODE_ITERATOR_TYPE,
      null,
    );
    let node = result.iterateNext();
    while (node) {
      if (node === element) index = count;
      count++;
      node = result.iterateNext();
    }
    return { count, index };
  },

  // Convert a single-key attribute object (the shape tree-builder
  // emits) into an XPath subpath chunk. The priority order matters:
  // attributes earlier in `SUBPATH_PRIORITY` win when the object
  // happens to carry several. `index` is the bare-tag fallback. The
  // legacy `subpath` first arg is kept for API stability and ignored.
  _getSubpath(_subpath, attr, tag) {
    if (attr == null) return '';
    for (const key of SUBPATH_PRIORITY) {
      if (key === 'class') {
        const v = attr.class;
        if (v != null && (typeof v === 'string' ? v.length > 0 : v.length > 0)) {
          return `/${tag}[@class="${v}"]`;
        }
        continue;
      }
      if (attr[key] != null) {
        return `/${tag}[@${key}="${attr[key]}"]`;
      }
    }
    if (attr.index != null) return `/${tag}`;
    return '';
  },
};

if (typeof exports !== 'undefined') exports.locator = locator;
