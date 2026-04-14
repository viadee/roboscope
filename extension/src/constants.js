/**
 * Shared constants for the RoboScope Recorder extension.
 *
 * Based on robotframework-recorder (GPL-3.0)
 * https://github.com/viadee/robotframework-recorder
 */

export const url = 'https://github.com/viadee/roboscope';

export const tab = { active: true, currentWindow: true };

export const logo = {
  stop: '/assets/mark-128.png',
  record: '/assets/btn-record.png',
  scan: '/assets/icon-target.png',
  action: '/assets/mark-128.png',
  pause: '/assets/icon-pause.png'
};

export const filename = 'robot_script.robot';

/** Default target library — unified across popup and background. */
export const DEFAULT_TARGET = 'Browser';

/** Default syntax mode. */
export const DEFAULT_SYNTAX = 'rpa';

export const statusMessage = {
  stop: 'Stopped',
  record: 'Recording action...',
  succesfulRecord: 'Recorded script',
  failedRecord: 'Recording failed. No actions were captured.',
  scan: 'Scanning html document...',
  failedScan: 'Scan failed. No active tab found.',
  failure: 'Operation failed. Please try refreshing the web page.',
  idle: 'Idle',
};

export const instruction = `RoboScope Recorder
  Generate a Robot Framework automation script by
  – Recording actions
  – Scanning the page for automatable inputs
   Automating automation`;

export const defaultLocatorOrder = ['for', 'name', 'id', 'title', 'href', 'class'];
