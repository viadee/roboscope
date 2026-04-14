// Centralized logger for the extension UI/background scripts.
// Using a single file makes it easy to control verbosity and
// avoids ESLint no-console warnings throughout the codebase.

const DEBUG = false;

const safeStringify = (v) => {
  try {
    return typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v);
  } catch (_e) {
    return String(v);
  }
};

const logger = {
  debug: (...args) => {
    if (!DEBUG) return;
    console.debug(...args);
  },
  info: (...args) => {
    console.info(...args);
  },
  warn: (...args) => {
    console.warn(...args);
  },
  error: (msg, ...rest) => {
    if (rest && rest.length) {
      const fmt = rest.map(safeStringify).join(' ');
      console.error(msg, fmt);
    } else {
      console.error(msg);
    }
  }
};

export default logger;
