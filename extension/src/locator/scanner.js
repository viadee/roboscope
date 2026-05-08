// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 viadee Unternehmensberatung AG.
//
// DOM scanner — walks an element subtree, classifies each element into
// a recordable action type, and synthesises an XPath locator + value
// payload per match. Public API:
//
//   scanner.parseNodes(out, root, attrs)  → recursive scan, fills `out`
//   scanner.parseNode(time, node, attrs)  → one-shot for a single node
//   scanner.limit                          → mutable budget; default 1000
//
// Implementation: clean-room rewrite (RECORDER-LICENSE) using the
// classifier + tree-builder + locator helpers in the same directory.
//
/* global Node builder locator classifier */

const scanner = {
  limit: 1000,

  parseNodes(out, root, attrs) {
    if (root === undefined || root === null) return out;
    if (this.limit <= 0) return out;
    this.limit -= 1;

    const hash = classifier(root);
    if (hash) {
      const tree = builder.build(root, attrs, []);
      // Pass `attrs` as the 4th arg even though `locator.build` only
      // uses three — preserves the long-standing call signature so
      // downstream stubs / future overrides keep working.
      hash.path = locator.build(tree, root, hash.type, attrs);
      out.push(hash);
    }

    const kids = root.childNodes;
    if (kids) {
      for (let i = 0; i < kids.length; i++) {
        const k = kids[i];
        if (k && k.nodeType === Node.ELEMENT_NODE) {
          this.parseNodes(out, k, attrs);
        }
      }
    }
    return out;
  },

  parseNode(time, node, attrs) {
    if (node === undefined || node === null) return {};
    const hash = classifier(node) || { type: 'default' };
    const tree = builder.build(node, attrs, []);
    hash.time = time;
    hash.path = locator.build(tree, node, hash.type);
    return hash;
  },
};

if (typeof exports !== 'undefined') module.exports.scanner = scanner;
