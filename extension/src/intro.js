/**
 * Modern lightweight intro/tutorial system
 * Replaces ChardinJS with a minimal, modern implementation
 */

export class IntroTour {
  constructor() {
    this.isActive = false;
    this.currentStep = 0;
    this.steps = [];
    this.overlay = null;
    this.tooltip = null;
  }

  /**
   * Initialize tour from data-intro attributes
   */
  init() {
    const elements = document.querySelectorAll('[data-intro]');
    this.steps = Array.from(elements).map(el => ({
      element: el,
      intro: el.getAttribute('data-intro'),
      position: el.getAttribute('data-position') || 'bottom'
    }));
  }

  /**
   * Start or toggle the tour
   */
  toggle() {
    if (this.isActive) {
      this.stop();
    } else {
      this.start();
    }
  }

  /**
   * Start the tour
   */
  start() {
    if (this.steps.length === 0) return;

    this.isActive = true;
    this.currentStep = 0;
    this._createUI();
    this._showStep(0);
  }

  /**
   * Stop the tour
   */
  stop() {
    this.isActive = false;
    this._removeUI();
  }

  /**
   * Show specific step
   */
  _showStep(index) {
    if (index >= this.steps.length) {
      this.stop();
      return;
    }

    this.currentStep = index;
    const step = this.steps[index];
    const rect = step.element.getBoundingClientRect();

    const outerShadow = '0 0 0 9999px rgba(0, 0, 0, 0.7)';
    const innerShadow = 'inset 0 0 0 1px rgba(0, 192, 181, 0.3)';
    this.overlay.style.boxShadow = `${outerShadow}, ${innerShadow}`;
    this.overlay.style.top = `${rect.top}px`;
    this.overlay.style.left = `${rect.left}px`;
    this.overlay.style.width = `${rect.width}px`;
    this.overlay.style.height = `${rect.height}px`;
    this.overlay.style.borderRadius = '4px';

    this._positionTooltip(step, rect);
    this.tooltip.querySelector('.intro-text').textContent = step.intro;

    const nextBtn = this.tooltip.querySelector('.intro-next');
    nextBtn.textContent = index === this.steps.length - 1 ? '✓ Done' : 'Next ›';
  }

  /**
   * Position tooltip relative to element
   */
  _positionTooltip(step, rect) {
    const padding = 12;
    let top; let left;
    const tooltipWidth = 280;
    const tooltipHeight = 100;

    switch (step.position) {
      case 'bottom':
        top = rect.bottom + padding;
        {
          const centered = rect.left + rect.width / 2 - tooltipWidth / 2;
          const maxLeft = window.innerWidth - tooltipWidth - 10;
          left = Math.max(0, Math.min(centered, maxLeft));
        }
        break;
      case 'top':
        top = rect.top - tooltipHeight - padding;
        {
          const centered = rect.left + rect.width / 2 - tooltipWidth / 2;
          const maxLeft = window.innerWidth - tooltipWidth - 10;
          left = Math.max(0, Math.min(centered, maxLeft));
        }
        break;
      case 'left':
        top = rect.top + rect.height / 2 - tooltipHeight / 2;
        left = rect.left - tooltipWidth - padding;
        break;
      case 'right':
        top = rect.top + rect.height / 2 - tooltipHeight / 2;
        left = rect.right + padding;
        break;
      default:
        top = rect.bottom + padding;
        left = Math.max(0, Math.min(rect.left, window.innerWidth - tooltipWidth - 10));
    }

    this.tooltip.style.top = `${top}px`;
    this.tooltip.style.left = `${left}px`;
  }

  /**
   * Create UI elements (overlay and tooltip)
   */
  _createUI() {
    this.overlay = document.createElement('div');
    this.overlay.className = 'intro-overlay';
    this.overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      z-index: 9998;
      transition: all 0.3s ease;
    `;
    document.body.appendChild(this.overlay);

    this.tooltip = document.createElement('div');
    this.tooltip.className = 'intro-tooltip';
    this.tooltip.style.cssText = `
      position: fixed;
      z-index: 9999;
      background: white;
      padding: 12px 16px;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      max-width: 280px;
      font-size: 14px;
      line-height: 1.4;
      transition: all 0.3s ease;
      border-left: 4px solid #00c0b5;
    `;

    const introText = document.createElement('div');
    introText.className = 'intro-text';
    introText.style.cssText = 'margin-bottom: 12px; color: #333;';

    const actions = document.createElement('div');
    actions.style.cssText = 'display: flex; gap: 8px; justify-content: flex-end;';

    const skipBtn = document.createElement('button');
    skipBtn.className = 'intro-skip';
    skipBtn.textContent = 'Skip';
    skipBtn.style.padding = '4px 12px';
    skipBtn.style.border = 'none';
    skipBtn.style.background = '#f0f0f0';
    skipBtn.style.color = '#666';
    skipBtn.style.borderRadius = '4px';
    skipBtn.style.cursor = 'pointer';
    skipBtn.style.fontSize = '12px';

    const nextBtn = document.createElement('button');
    nextBtn.className = 'intro-next';
    nextBtn.textContent = 'Next ›';
    nextBtn.style.padding = '4px 12px';
    nextBtn.style.border = 'none';
    nextBtn.style.background = '#00c0b5';
    nextBtn.style.color = 'white';
    nextBtn.style.borderRadius = '4px';
    nextBtn.style.cursor = 'pointer';
    nextBtn.style.fontSize = '12px';
    nextBtn.style.fontWeight = '500';

    actions.appendChild(skipBtn);
    actions.appendChild(nextBtn);
    this.tooltip.appendChild(introText);
    this.tooltip.appendChild(actions);

    document.body.appendChild(this.tooltip);

    this.overlay.addEventListener('click', () => this.stop());
    this.tooltip.querySelector('.intro-skip').addEventListener('click', () => this.stop());
    this.tooltip.querySelector('.intro-next').addEventListener('click', () => {
      this.currentStep++;
      if (this.currentStep < this.steps.length) {
        this._showStep(this.currentStep);
      } else {
        this.stop();
      }
    });

    this._keyHandler = (e) => {
      if (!this.isActive) return;
      if (e.key === 'Escape') this.stop();
      if (e.key === 'ArrowRight') {
        this.currentStep++;
        if (this.currentStep < this.steps.length) {
          this._showStep(this.currentStep);
        } else {
          this.stop();
        }
      }
      if (e.key === 'ArrowLeft' && this.currentStep > 0) {
        this.currentStep--;
        this._showStep(this.currentStep);
      }
    };
    document.addEventListener('keydown', this._keyHandler);
  }

  /**
   * Remove UI elements
   */
  _removeUI() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
    if (this.tooltip) {
      this.tooltip.remove();
      this.tooltip = null;
    }
    if (this._keyHandler) {
      document.removeEventListener('keydown', this._keyHandler);
    }
  }
}
