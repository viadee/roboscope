# Tests ausführen

Das Projekt verwendet **Mocha** als Test-Framework mit **Chai** für Assertions.

## Voraussetzungen

Installieren Sie zuerst die Dependencies:

```bash
npm install
# oder
yarn install
```

## Test-Befehle

### 1. Tests ausführen (mit Linting)
```bash
npm test
# oder
yarn test
```

Dies führt aus:
1. ESLint zur Code-Qualitätsprüfung (`lint-fix`)
2. Mocha Tests mit nyan Reporter

### 2. Nur Tests ausführen (ohne Linting)
```bash
npm run test-local
# oder
yarn test-local
```

### 3. Tests mit Coverage
```bash
npm run test-coverage
# oder
yarn test-coverage
```

Zeigt die Code-Coverage an.

### 4. Nur Linting
```bash
npm run lint
# oder
yarn lint
```

Überprüft Code-Style mit ESLint.

### 5. Linting automatisch korrigieren
```bash
npm run lint-fix
# oder
yarn lint-fix
```

## Test-Struktur

Die Tests befinden sich im `test/` Verzeichnis:

```
test/
├── setup.js                    # Test-Setup (JSDOM, Chrome Mock, etc.)
├── options_spec.js             # Tests für options.js
├── translator/
│   └── robot-translator_spec.js    # Tests für Robot Translator
├── locator/
│   ├── xpath-locator_spec.js      # Tests für XPath Locator
│   ├── classifier_spec.js         # Tests für Classifier
│   ├── scanner_spec.js            # Tests für Scanner
│   └── tree-builder_spec.js       # Tests für Tree Builder
└── integration/
    └── extension_install_spec.js   # Integration Tests
```

## Test-Framework

- **Mocha**: Test Runner
- **Chai**: Assertion Library
- **Sinon**: Mocking/Stubbing
- **JSDOM**: DOM Simulation
- **NYC**: Code Coverage

## Beispiel: Test ausführen

```bash
# Alle Tests
npm test

# Nur Locator Tests
npm run test-local -- test/locator/**/*.js

# Mit Coverage
npm run test-coverage
```

## Debugging

```bash
# Tests mit Node Inspector
node --inspect-brk ./node_modules/.bin/mocha -r test/setup.js test/**/*.js

# Dann öffnen Sie: chrome://inspect
```

## Tipps

- Tests verwenden **Chai** für Assertions: `expect(...).to.equal(...)`
- Mocks werden mit **Sinon** erstellt
- Setup.js mockt Chrome API für Tests
- Code-Coverage wird in `.nyc_output/` gespeichert
