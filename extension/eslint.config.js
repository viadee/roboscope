const globals = require("globals");

module.exports = [
  {
    ignores: ["node_modules/", "coverage/", "script/"],
  },
  {
    files: ["src/logger.js"],
    rules: {
      "no-console": "off",
    },
  },
  {
    files: ["src/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        chrome: "readonly",
      },
    },
    rules: {
      "comma-dangle": ["error", "only-multiline"],
      "max-len": ["error", { code: 120, comments: 120 }],
      "no-template-curly-in-string": "off",
      "no-plusplus": "off",
      "guard-for-in": "off",
      "prefer-destructuring": "off",
      "no-else-return": ["warn", { allowElseIf: true }],
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" }],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
  {
    files: ["test/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.mocha,
        ...globals.node,
        chrome: "readonly",
      },
    },
    rules: {
      "comma-dangle": ["error", "only-multiline"],
      "max-len": ["error", { code: 150, comments: 150 }],
      "no-template-curly-in-string": "off",
      "no-plusplus": "off",
      "guard-for-in": "off",
      "prefer-destructuring": "off",
      "no-else-return": ["warn", { allowElseIf: true }],
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
  {
    files: ["*.config.js", "*.config.mjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.node,
      },
    },
  },
];
