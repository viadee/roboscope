/* global document chrome scanner XPathResult Node */

const host = chrome;
let strategyList = [];

/*
var observer = new MutationObserver(recordMutate);
var config = { attributes: true, characterData: true, subtree: true, childList: true};
var config = { attributes: true, characterData: true, subtree: true };
childList: Set to true to observe additions and removals of the target node's child elements (including text nodes).
attributes: Set to true if mutations to target's attributes are to be observed.
characterData: Set to true if mutations to target's data are to be observed.
subtree: Set to true if mutations to not just target, but also target's descendants are to be observed
attributeOldValue: true if recording attributes is set to true and target's attribute value before the mutation
characterDataOldValue: true if recording characterData is set to true and target's data before the mutation
attributeFilter: true if observing an array of attribute local names (without namespace) if not all attribute mutations
*/
host.runtime.sendMessage({ operation: 'load' });

function getTime() {
  return new Date().getTime();
}

function handleByChange(type) {
  return ['text', 'file', 'select'].some(n => type === n);
}

const debug = false;
const logger = debug ? {
  debug: (data) => {
     
    console.debug(data);
  },
  error: (data) => {
     
    console.error(data);
  }
} : {
  debug: (_) => {},
  error: (_) => {},
};

function recordChange(event) {
  logger.debug('Tab recorded event: ', event);
  const attr = scanner.parseNode(getTime(), event.target, strategyList);

  if (handleByChange(attr.type)) {
    Object.assign(attr, { trigger: 'change' });
    host.runtime.sendMessage({ operation: 'append', script: attr });
  }
}

function recordClick(event) {
  logger.debug('Tab recorded event: ', event);
  const attr = scanner.parseNode(getTime(), event.target, strategyList);

  if (!handleByChange(attr.type)) {
    Object.assign(attr, { trigger: 'click' });
    host.runtime.sendMessage({ operation: 'append', script: attr });
  }
}

function xpathValidation(xpath) {
  // TODO: when creating new xpath highlights clear old ones
  let xpathResult;
  try {
    xpathResult = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE);
  } catch (error) {
    host.runtime.sendMessage({ operation: 'display', message: error.toString() });
    console.error('RF Recorder XPath error:', error);
  }
  if (!xpathResult) return;
  host.runtime.sendMessage({ operation: 'display', message: `XPath is valid, matches: ${xpathResult.snapshotLength}` });
  logger.debug(xpathResult);
  const options = {
    dur: 5000,
    wdt: '2px',
    stl: 'dotted',
    clr: '#6C50FA'
  };
  for (let i = 0; i < xpathResult.snapshotLength; i++) {
    const node = xpathResult.snapshotItem(i);
    logger.debug(node);
    const e = node;
    // see https://developer.mozilla.org/en-US/docs/Web/API/Node/nodeType for list of possible `nodeType`s
    if (e.nodeType === Node.ELEMENT_NODE) {
      const d = document.createElement('div');
      d.className = 'robotframework-recorder-highlight';
      d.appendChild(document.createTextNode(''));
      d.style.position = 'fixed';
      const rect = e.getBoundingClientRect();
      d.style.top = `${rect.top}px`;
      d.style.left = `${rect.left}px`;
      d.style.width = `${rect.width}px`;
      d.style.height = `${rect.height}px`;
      d.style.border = `${options.wdt || '1px'} ${options.stl || 'dotted'} ${options.clr || 'blue'}`;
      document.body.appendChild(d);
      setTimeout(() => {
        d.remove();
      }, options.dur || 5000);
    } else {
      logger.debug('Node was not an element ', node);
    }
  }
}
const defaultLocatorOrder = ['for', 'name', 'id', 'title', 'href', 'class'];

host.runtime.onMessage.addListener((request, sender, sendResponse) => {
  logger.debug('Tab received message: ', request);
  if (request.operation === 'record') {
    strategyList = request.locators || defaultLocatorOrder;
    strategyList.push('index');
    document.addEventListener('change', recordChange, true);
    document.addEventListener('click', recordClick, true);
    sendResponse({ ok: true, status: 'record listeners attached' });
  } else if (request.operation === 'stop') {
    document.removeEventListener('change', recordChange, true);
    document.removeEventListener('click', recordClick, true);
    sendResponse({ ok: true, status: 'record listeners attached' });
  } else if (request.operation === 'scan') {
    strategyList = request.locators || defaultLocatorOrder;
    strategyList.push('index');
    document.removeEventListener('change', recordChange, true);
    document.removeEventListener('click', recordClick, true);

    scanner.limit = 1000;
    const array = scanner.parseNodes([], document.body, strategyList);
    host.runtime.sendMessage({ operation: 'action', scripts: array });
    sendResponse({ ok: true, status: 'record listeners attached' });
  } else if (request.operation === 'xpath-validate') {
    xpathValidation(request.xpath);
    sendResponse({ ok: true });
  }
});
