/** Movable card labels and their websocket updates. Player cards stay in layout. */
(function () {
    const px = (value) => `${Math.round(value)}px`;
    const coord = (el, side) => parseInt(el.style[side], 10) || 0;
    let drag = null;
    const mutedResize = new WeakMap();
    const lastSize = new WeakMap();

    function send(message) {
        const transport = document.getElementById('board-transport');
        if (!transport) return;
        window.mgBoardMsg = message;
        htmx.trigger(transport, 'board-move');
    }

    function transform(label) {
        const input = label.querySelector('textarea');
        return {
            x: coord(label, 'left'), y: coord(label, 'top'),
            width: Math.round(input.offsetWidth), height: Math.round(input.offsetHeight),
        };
    }

    function clamp(label, x, y) {
        const card = label.closest('[data-card]');
        if (!card) return { x, y };
        return {
            x: Math.max(-label.offsetWidth + 32, Math.min(x, card.offsetWidth - 32)),
            y: Math.max(-label.offsetHeight + 24, Math.min(y, card.offsetHeight - 24)),
        };
    }

    document.addEventListener('mousedown', (event) => {
        if (event.button !== 0 || !event.target.closest('.mg-label-handle')) return;
        const label = event.target.closest('[data-drag="label"]');
        if (!label) return;
        event.preventDefault();
        drag = { label, x: event.clientX, y: event.clientY,
                 left: coord(label, 'left'), top: coord(label, 'top') };
        label.classList.add('mg-dragging');
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (event) => {
        if (!drag) return;
        const at = clamp(drag.label, drag.left + event.clientX - drag.x, drag.top + event.clientY - drag.y);
        drag.label.style.left = px(at.x);
        drag.label.style.top = px(at.y);
    });

    function endDrag() {
        if (!drag) return;
        const label = drag.label;
        drag = null;
        label.classList.remove('mg-dragging');
        document.body.style.userSelect = '';
        send({ type: 'label_position', owner_uid: label.dataset.uid, ...transform(label) });
    }

    document.addEventListener('mouseup', endDrag);
    window.addEventListener('blur', endDrag);

    const resizeObserver = new ResizeObserver((entries) => {
        for (const { target: input } of entries) {
            const label = input.closest('[data-drag="label"]');
            const size = `${input.offsetWidth}x${input.offsetHeight}`;
            const previous = lastSize.get(input);
            lastSize.set(input, size);
            if (!label || previous === undefined || previous === size || Date.now() < (mutedResize.get(input) || 0)) continue;
            clearTimeout(label.resizeTimer);
            label.resizeTimer = setTimeout(
                () => send({ type: 'label_position', owner_uid: label.dataset.uid, ...transform(label) }), 300);
        }
    });

    function watchLabels() {
        document.querySelectorAll('[data-drag="label"] textarea').forEach((input) => resizeObserver.observe(input));
    }

    window.onBoardMessage = function (event) {
        if (!isJson(event.detail.message)) return;
        const message = JSON.parse(event.detail.message);
        if (message.type === 'label_text') {
            const input = document.querySelector(`textarea[data-label-text="${message.owner_uid}"]`);
            if (input && document.activeElement !== input) input.value = message.label;
        } else if (message.type === 'label_position') {
            const label = document.querySelector(`[data-label="${message.owner_uid}"]`);
            if (!label || drag?.label === label) return;
            const input = label.querySelector('textarea');
            const at = clamp(label, message.x, message.y);
            label.style.left = px(at.x);
            label.style.top = px(at.y);
            if (message.width && message.height) {
                mutedResize.set(input, Date.now() + 500);
                input.style.width = px(message.width);
                input.style.height = px(message.height);
            }
        } else return;
        event.preventDefault();
    };

    for (const event of ['DOMContentLoaded', 'pageshow', 'htmx:historyRestore', 'htmx:afterSwap']) {
        document.addEventListener(event, watchLabels);
    }
})();
