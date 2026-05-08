# RoboScope Recorder

> A Chrome browser extension that records user interactions and generates [Robot Framework](http://robotframework.org/) test scripts — with optional RoboScope integration for seamless test management.

**Based on [robotframework-recorder](https://github.com/viadee/robotframework-recorder)** (feature/ui-redesign branch), originally forked from [Robotcorder](https://github.com/sohwendy/Robotcorder) by @sohwendy.

## License

This extension is licensed under **GPL-3.0** (see [LICENSE](./LICENSE)).  
The RoboScope core application (backend/frontend) is licensed under Apache-2.0.  
See [NOTICE](./NOTICE) for full attribution details.

## Features

### Core Recording
- Record user actions (clicks, form inputs, selections) and generate `.robot` files
- Scan HTML pages for interactive elements
- Validate XPath selectors with visual highlights
- Choose between **SeleniumLibrary** or **Browser** (Playwright) keyword output
- Choose between **RPA** (Task) or **Testing** (Test Case) syntax
- Smart locator generation with configurable strategies (id, name, class, href, etc.)

### UI (Side Panel)
- Chrome Side Panel integration for non-intrusive recording
- Live preview of recorded actions during capture
- Structured keyword editor with named parameters
- Context menu for assertions, control structures, and keyword extraction
- Resource file export for reusable keywords

### RoboScope Integration
- Connect to a RoboScope server instance via API token (Options page)
- Select target project from the extension (Options page project dropdown)
- Stream recorded events to RoboScope backend in real-time (`POST /recordings/{id}/event`)
- Connection status indicator in popup (green = connected, grey = disconnected)
- Dual mode: works standalone (local .robot generation) or connected to RoboScope
- *Planned:* AI-enhanced keyword selection using rf-mcp keyword knowledge
- *Planned:* Save generated `.robot` files directly into RoboScope project repositories

## Development Setup

```bash
# Install dependencies
npm install

# Run linter
npm run lint

# Run unit tests
npm run test-local

# Run tests with coverage
npm run test-coverage

# Run E2E tests (requires Playwright browsers)
npm run test-e2e
```

### Load as unpacked extension

1. Go to `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" and select this `extension/` directory

## Architecture

```
extension/
├── manifest.json              # Chrome Extension Manifest v3 (side panel, context menus)
├── src/
│   ├── service-worker.js      # Background service worker entry (ES module)
│   ├── background.js          # Message hub, state management, script generation
│   ├── content.js             # DOM event listeners (click, change)
│   ├── context-menu.js        # Right-click context menu actions
│   ├── keyword-spec.js        # Structured keyword parameter definitions
│   ├── popup.html/js          # Side panel UI (recording, preview, settings)
│   ├── roboscope-client.js     # RoboScope API client (connection, recordings, events)
│   ├── options.html/js        # Settings page (locators + RoboScope connection)
│   ├── actions-view.html/js   # Recorded actions viewer/editor
│   ├── locator/               # Locator generation engine
│   │   ├── classifier.js      # Element type classification
│   │   ├── scanner.js         # DOM traversal
│   │   ├── tree-builder.js    # DOM path construction
│   │   └── xpath-locator.js   # XPath expression builder
│   └── translator/
│       └── robot-translator.js  # Action -> Robot Framework keyword mapping
├── assets/                    # Icons, CSS, theme
├── test/                      # Unit tests (Mocha/Chai) + E2E tests (Playwright)
└── vendors/                   # Third-party vendored code
```

## Original Authors

- [@sohwendy](https://github.com/sohwendy) (Robotcorder)
- [@xylix](https://github.com/xylix) (robotframework-recorder)
- [viadee Unternehmensberatung AG](https://www.viadee.de/)
