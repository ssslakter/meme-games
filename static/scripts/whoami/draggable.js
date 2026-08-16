/** Local-only movable panels, currently the player's personal notes.
 *  One delegated listener: the panel is re-rendered by websocket swaps, and
 *  per-element registration kept missing the copy that replaced it.
 *  Placement and size live here rather than in game state - a swap replaces the
 *  element outright, so the inline styles have to be re-applied afterwards. */
(function () {
    const KEY = 'meme-games.notes-panel';
    let drag = null;
    let placement = read();

    function read() {
        try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
    }

    function write() {
        try { localStorage.setItem(KEY, JSON.stringify(placement)); } catch (e) { }
    }

    function apply(panel) {
        const notes = panel.querySelector('.mg-notes');
        if (notes && placement.width) {
            notes.style.width = placement.width;
            notes.style.height = placement.height;
        }
        if (placement.left == null) return;
        panel.style.transform = 'none';
        panel.style.bottom = 'auto';
        panel.style.left = `${Math.max(0, Math.min(placement.left, innerWidth - panel.offsetWidth))}px`;
        panel.style.top = `${Math.max(0, Math.min(placement.top, innerHeight - panel.offsetHeight))}px`;
    }

    function restore() { document.querySelectorAll('.draggable-panel').forEach(apply); }

    document.addEventListener('pointerdown', (event) => {
        if (event.button !== 0 || !event.target.closest('.mg-notes-title')) return;
        const panel = event.target.closest('.draggable-panel');
        if (!panel) return;
        event.preventDefault();
        const rect = panel.getBoundingClientRect();
        panel.style.transform = 'none';
        panel.style.bottom = 'auto';
        panel.style.left = `${rect.left}px`;
        panel.style.top = `${rect.top}px`;
        panel.classList.add('mg-panel-dragging');
        drag = { panel, x: event.clientX - rect.left, y: event.clientY - rect.top };
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('pointermove', (event) => {
        if (!drag) return;
        const x = Math.max(0, Math.min(event.clientX - drag.x, innerWidth - drag.panel.offsetWidth));
        const y = Math.max(0, Math.min(event.clientY - drag.y, innerHeight - drag.panel.offsetHeight));
        drag.panel.style.left = `${x}px`;
        drag.panel.style.top = `${y}px`;
        placement.left = x;
        placement.top = y;
    });

    function stop() {
        if (!drag) return;
        drag.panel.classList.remove('mg-panel-dragging');
        drag = null;
        document.body.style.userSelect = '';
        write();
    }

    document.addEventListener('pointerup', stop);
    document.addEventListener('pointercancel', stop);
    window.addEventListener('blur', stop);

    // The native resize gutter reports nothing but the inline width it just wrote,
    // and every drag of it ends in a pointerup somewhere inside the panel.
    document.addEventListener('pointerup', (event) => {
        const notes = event.target.closest('.mg-floating-notes > .mg-notes');
        if (!notes || !notes.style.width) return;
        placement.width = notes.style.width;
        placement.height = notes.style.height;
        write();
    });

    document.addEventListener('htmx:afterSwap', restore);
    document.addEventListener('htmx:oobAfterSwap', restore);
    document.addEventListener('htmx:load', restore);
    document.addEventListener('DOMContentLoaded', restore);
    restore();
})();
