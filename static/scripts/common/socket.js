// Best-effort lobby socket recovery. htmx already retries 1006/1012/1013.
// Anything else while the page is still up gets the same wrapper.reconnect,
// which only opens a new socket. htmx then flushes messages that never left the browser.
(function () {
  const HTMX_RETRY = { 1006: 1, 1012: 1, 1013: 1 };
  let generation = 0;

  function status(text, kind, ttl) {
    const mine = ++generation;
    let container = document.getElementById("mg-toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "mg-toast-container";
      container.className = "mg-toast-container";
      document.body.appendChild(container);
    }
    let el = document.getElementById("mg-socket-status");
    if (!el) {
      el = document.createElement("div");
      el.id = "mg-socket-status";
      el.setAttribute("role", "status");
      el.dataset.ui = "socket-status";
      container.prepend(el);
    }
    el.className = "mg-toast mg-toast-" + kind;
    el.textContent = text;
    if (ttl) setTimeout(() => { if (generation === mine) el.remove(); }, ttl);
  }

  function socketElt(event) {
    const elt = event.target;
    if (!elt || elt.nodeType !== 1 || !elt.hasAttribute("ws-connect")) return null;
    if (!document.body.contains(elt)) return null;
    return elt;
  }

  document.addEventListener("htmx:wsClose", (event) => {
    const elt = socketElt(event);
    if (!elt) return;
    elt._mgDown = true;
    status("Connection lost. Reconnecting…", "warning");
    const code = event.detail && event.detail.event && event.detail.event.code;
    if (HTMX_RETRY[code]) return;
    const wrapper = event.detail && event.detail.socketWrapper;
    if (!wrapper || typeof wrapper.reconnect !== "function") return;
    elt._mgRetries = (elt._mgRetries || 0) + 1;
    if (elt._mgRetries > 6) {
      status("Connection lost.", "error");
      return;
    }
    clearTimeout(elt._mgReconnect);
    const delay = Math.min(8000, 400 * 2 ** (elt._mgRetries - 1));
    elt._mgReconnect = setTimeout(() => {
      if (document.body.contains(elt)) wrapper.reconnect();
    }, delay);
  });

  document.addEventListener("htmx:wsOpen", (event) => {
    const elt = socketElt(event);
    if (!elt || !elt._mgDown) return;
    clearTimeout(elt._mgReconnect);
    elt._mgRetries = 0;
    elt._mgDown = false;
    status("Reconnected", "success", 2000);
  });
})();
