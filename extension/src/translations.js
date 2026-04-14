const translations = {
  en: {
    // Buttons
    record: 'Record',
    stop: 'Stop',
    resume: 'Resume',
    pause: 'Pause',
    scanPage: 'Scan Page',
    validateXPath: 'Validate XPath',
    copy: 'Copy',
    download: 'Download',
    clear: 'Clear',
    update: 'Update',
    reset: 'Reset',

    // Titles
    recordTitle: 'Record user action',
    stopTitle: 'Stop the recording',
    resumeTitle: 'Resume with the recording',
    pauseTitle: 'Pause the recording',
    scanPageTitle: 'Scan entire page',
    validateXPathTitle: 'Show/hide XPath console',
    infoTitle: 'Toggle instructions',
    settingsTitle: 'show/hide settings',
    copyTitle: 'Copy to clipboard',
    downloadTitle: 'Download test script',
    clearTitle: 'Clear script',
    xpathPlaceholder: '//xpath-to-validate',

    // Data-intro
    recordIntro: 'Start recording actions',
    scanIntro: 'Generate a script referencing interactive elements on the page',
    xpathIntro: 'Open interactive XPath console',
    settingsIntro: 'Settings',

    // Settings Panel
    targetLibrary: 'Target Library',
    selenium: 'RPA.Browser.Selenium / SeleniumLibrary',
    rfBrowser: 'RobotFramework Browser',
    targetSyntax: 'Target RF Syntax',
    rpa: 'RPA (Tasks)',
    testAutomation: 'Test Automation (Test cases)',
    advancedSettings: 'Advanced settings',
    addSleep: 'Add a sleep after each action (for creating easy-to-showcase demo scripts)',
    checkPageContains: 'Check page contains element before performing the action',

    // Options Page
    customLocators: 'Custom Locators',
    customLocatorsHint: 'Add your own flavoured locators! Separate with a commas.',
    language: 'Language',

    // Default message
    recordOrScan: 'Record or Scan',
    // Actions-View specific
    refresh: 'Refresh',
    exportRobot: 'Export .robot',
    exportJson: 'Export JSON',
    copyScript: 'Copy Script',
    noActions: 'No actions available',
    lineCopied: 'Line copied',
    lineExported: 'Line exported',
    copyThisLine: 'Copy this line',
    exportThisLine: 'Export this line as text',
    editUnderlying: 'Edit underlying action',
    onlyPathEditable: 'Only path lines can be edited',
    cancel: 'Cancel',
    save: 'Save',
    edit: 'Edit',
    actionSaved: 'Action saved',
    saveFailed: 'Failed to save action',
    scriptAvailable: 'Script available',
    noScriptGenerated: 'No script generated',
    exportStarted: 'Export started',
    exportFailed: 'Export failed',
    // Page labels
    pageTitle: 'Recorder - Actions Viewer',
    actionsHeading: 'Recorded actions',
    actionsListPlaceholder: 'Actions will appear here',
    // Extract & Resource
    extractKeyword: 'Extract Keyword',
    exportResource: 'Export .resource',
    deleteThisLine: 'Delete this line',
    // Popup specific
    addLine: 'Add line',
    addLineTitle: 'Add new line'
  },
  de: {
    // Buttons
    record: 'Aufzeichnen',
    stop: 'Stopp',
    resume: 'Fortsetzen',
    pause: 'Pause',
    scanPage: 'Seite scannen',
    validateXPath: 'XPath validieren',
    copy: 'Kopieren',
    download: 'Herunterladen',
    clear: 'Löschen',
    update: 'Aktualisieren',
    reset: 'Zurücksetzen',

    // Titles
    recordTitle: 'Benutzeraktionen aufzeichnen',
    stopTitle: 'Aufzeichnung beenden',
    resumeTitle: 'Aufzeichnung fortsetzen',
    pauseTitle: 'Aufzeichnung pausieren',
    scanPageTitle: 'Gesamte Seite scannen',
    validateXPathTitle: 'XPath-Konsole anzeigen/verbergen',
    infoTitle: 'Anweisungen anzeigen/verbergen',
    settingsTitle: 'Einstellungen anzeigen/verbergen',
    copyTitle: 'In Zwischenablage kopieren',
    downloadTitle: 'Testskript herunterladen',
    clearTitle: 'Skript löschen',
    xpathPlaceholder: '//xpath-zum-validieren',

    // Data-intro
    recordIntro: 'Aktionen aufzeichnen starten',
    scanIntro: 'Skript generieren, das auf interaktive Elemente auf der Seite verweist',
    xpathIntro: 'Interaktive XPath-Konsole öffnen',
    settingsIntro: 'Einstellungen',

    // Settings Panel
    targetLibrary: 'Zielbibliothek',
    selenium: 'RPA.Browser.Selenium / SeleniumLibrary',
    rfBrowser: 'RobotFramework Browser',
    targetSyntax: 'RF-Zielsyntax',
    rpa: 'RPA (Tasks)',
    testAutomation: 'Testautomatisierung (Testfälle)',
    advancedSettings: 'Erweiterte Einstellungen',
    addSleep: 'Nach jeder Aktion eine Pause hinzufügen (zum Erstellen von leicht demonstrierbaren Demo-Skripten)',
    checkPageContains: 'Überprüfen, ob die Seite das Element enthält, bevor die Aktion ausgeführt wird',

    // Options Page
    customLocators: 'Benutzerdefinierte Locatoren',
    customLocatorsHint: 'Fügen Sie eigene Locatoren hinzu. Mit Kommas trennen.',
    language: 'Sprache',

    // Default message
    recordOrScan: 'Aufzeichnen oder Scannen',
    // Actions-View specific
    refresh: 'Aktualisieren',
    exportRobot: 'Export .robot',
    exportJson: 'Export JSON',
    copyScript: 'Skript kopieren',
    noActions: 'Keine Aktionen vorhanden',
    lineCopied: 'Zeile kopiert',
    lineExported: 'Zeile exportiert',
    copyThisLine: 'Diese Zeile kopieren',
    exportThisLine: 'Diese Zeile als Text exportieren',
    editUnderlying: 'Zugehörige Aktion bearbeiten',
    onlyPathEditable: 'Nur Pfadzeilen können bearbeitet werden',
    cancel: 'Abbrechen',
    save: 'Speichern',
    edit: 'Bearbeiten',
    actionSaved: 'Aktion gespeichert',
    saveFailed: 'Fehler beim Speichern',
    scriptAvailable: 'Script verfügbar',
    noScriptGenerated: 'Kein Script generiert',
    exportStarted: 'Export gestartet',
    exportFailed: 'Export fehlgeschlagen',
    // Extract & Resource
    extractKeyword: 'Keyword extrahieren',
    exportResource: 'Export .resource',
    deleteThisLine: 'Diese Zeile löschen',
    // Page labels
    pageTitle: 'Recorder - Aktionen',
    actionsHeading: 'Aufgenommene Aktionen',
    actionsListPlaceholder: 'Aktionen werden hier angezeigt',
    // Popup specific
    addLine: 'Zeile hinzufügen',
    addLineTitle: 'Neue Zeile hinzufügen'
  }
};

/**
 * Get the current language setting or detect from browser locale
 */
export async function getCurrentLanguage() {
  const result = await chrome.storage.local.get({ language: null });
  if (result.language) {
    return result.language;
  }
  const browserLang = chrome.i18n.getUILanguage();
  return browserLang.startsWith('de') ? 'de' : 'en';
}

/**
 * Get translated string for given key and language
 */
export function t(key, language = 'en') {
  if (translations[language] && translations[language][key]) {
    return translations[language][key];
  }
  if (translations.en[key]) {
    return translations.en[key];
  }
  return key;
}

/**
 * Get all translations for a language
 */
export function getTranslations(language = 'en') {
  return translations[language] || translations.en;
}

/**
 * Set the current language
 */
export function setLanguage(language) {
  chrome.storage.local.set({ language });
}
