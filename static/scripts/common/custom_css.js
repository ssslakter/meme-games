(function () {
  const CSS_KEY = 'meme-games.custom-css';
  const ENABLED_KEY = 'meme-games.custom-css-enabled';
  const STYLE_ID = 'custom-css';

  function settingsPage() {
    return location.pathname === '/me' || location.pathname === '/me/';
  }

  function enabled() {
    return localStorage.getItem(ENABLED_KEY) !== 'false';
  }

  function applyCustomCss() {
    let style = document.getElementById(STYLE_ID);
    if (settingsPage() || !enabled()) {
      style?.remove();
      return;
    }
    if (!style) {
      style = document.createElement('style');
      style.id = STYLE_ID;
      document.head.append(style);
    }
    const css = localStorage.getItem(CSS_KEY) || '';
    style.textContent = containsImport(css) ? '' : css;
  }

  function containsImport(css) {
    const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '');
    const unescaped = withoutComments.replace(/\\([0-9a-f]{1,6}\s?|.)/gi, (_, value) => {
      const hex = value.trim();
      if (!/^[0-9a-f]+$/i.test(hex)) return value;
      const codePoint = parseInt(hex, 16);
      return String.fromCodePoint(codePoint <= 0x10ffff ? codePoint : 0xfffd);
    });
    return /@\s*import\b/i.test(unescaped);
  }

  function loadEditor() {
    const editor = document.getElementById('custom-css-editor');
    const checkbox = document.getElementById('custom-css-enabled');
    if (!editor || !checkbox) return;
    editor.value = localStorage.getItem(CSS_KEY) || '';
    checkbox.checked = enabled();
  }

  window.saveCustomCss = function (event) {
    event.preventDefault();
    const css = document.getElementById('custom-css-editor').value;
    const error = document.getElementById('custom-css-error');
    const status = document.getElementById('custom-css-status');
    error.textContent = '';
    status.textContent = '';
    if (containsImport(css)) {
      error.textContent = '@import is not supported. Paste the theme CSS directly.';
      return false;
    }
    localStorage.setItem(CSS_KEY, css);
    localStorage.setItem(ENABLED_KEY, String(document.getElementById('custom-css-enabled').checked));
    status.textContent = 'Saved. Open another page to see your changes.';
    return false;
  };

  window.clearCustomCss = function () {
    localStorage.removeItem(CSS_KEY);
    document.getElementById('custom-css-editor').value = '';
    document.getElementById('custom-css-error').textContent = '';
    document.getElementById('custom-css-status').textContent = 'Custom CSS cleared.';
  };

  window.applyCustomCss = applyCustomCss;
  window.customCssContainsImport = containsImport;
  applyCustomCss();
  document.addEventListener('DOMContentLoaded', loadEditor);
  document.addEventListener('htmx:afterSwap', () => {
    applyCustomCss();
    loadEditor();
  });
})();
