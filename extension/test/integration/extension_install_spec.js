 
 
 
const { chromium } = require('playwright');
const pathLib = require('path');
const assert = require('assert');

describe('playwright-integration-tests', (async function () {
  this.timeout(10000);
  let context;

  before(async () => {
    const pathToExtension = pathLib.join(__dirname, '../../');
    const userDataDir = 'test-user-data-dir';
    context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        `--disable-extensions-except=${pathToExtension}`,
        `--load-extension=${pathToExtension}`
      ]
    });
  });

  after(async () => context.close());

  it('service worker should be activated', async function () {
    this.timeout(20000);
    const [worker] = context.serviceWorkers().length
      ? context.serviceWorkers()
      : [await context.waitForEvent('serviceworker')];

    assert.ok(worker, 'Service worker not found');
    console.log('Service worker loaded from', worker.url());
  });
}));
