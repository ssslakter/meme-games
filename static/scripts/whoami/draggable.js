/** Local-only movable panels, currently the player's personal notes.
 *  One delegated listener: the panel is re-rendered by websocket swaps, and
 *  per-element registration kept missing the copy that replaced it. */
(function () {
    let drag = null;

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
    });

    function stop() {
        if (!drag) return;
        drag.panel.classList.remove('mg-panel-dragging');
        drag = null;
        document.body.style.userSelect = '';
    }

    document.addEventListener('pointerup', stop);
    document.addEventListener('pointercancel', stop);
    window.addEventListener('blur', stop);
})();
