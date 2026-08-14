/** Local-only movable panels, currently the player's personal notes. */
(function () {
    let drag = null;

    function initialize() {
        document.querySelectorAll('.draggable-panel:not([data-draggable-ready])').forEach((panel) => {
            panel.dataset.draggableReady = 'true';
            panel.addEventListener('mousedown', (event) => {
                if (event.button !== 0 || event.target.closest('textarea, input, button, a')) return;
                event.preventDefault();
                const rect = panel.getBoundingClientRect();
                panel.style.transform = 'none';
                panel.style.left = `${rect.left}px`;
                panel.style.top = `${rect.top}px`;
                panel.style.cursor = 'grabbing';
                drag = { panel, x: event.clientX - rect.left, y: event.clientY - rect.top };
                document.body.style.userSelect = 'none';
            });
        });
    }

    document.addEventListener('mousemove', (event) => {
        if (!drag) return;
        const x = Math.max(0, Math.min(event.clientX - drag.x, innerWidth - drag.panel.offsetWidth));
        const y = Math.max(0, Math.min(event.clientY - drag.y, innerHeight - drag.panel.offsetHeight));
        drag.panel.style.left = `${x}px`;
        drag.panel.style.top = `${y}px`;
    });

    function stop() {
        if (!drag) return;
        drag.panel.style.cursor = 'grab';
        drag = null;
        document.body.style.userSelect = '';
    }

    document.addEventListener('mouseup', stop);
    window.addEventListener('blur', stop);
    for (const event of ['DOMContentLoaded', 'pageshow', 'htmx:historyRestore', 'htmx:afterSwap']) {
        document.addEventListener(event, initialize);
    }
})();
