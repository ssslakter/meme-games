/** Movable card labels and their websocket updates. Player cards stay in layout. */
(function () {
    const RING = 80;
    const ANIMATION_MS = 500;
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

    function magnetTarget(label, wanted = transform(label)) {
        const card = label.closest('[data-card]');
        const input = label.querySelector('textarea');
        if (!card || !input) return wanted;
        const extraWidth = label.offsetWidth - input.offsetWidth;
        const extraHeight = label.offsetHeight - input.offsetHeight;
        const width = Math.min(wanted.width, card.offsetWidth - extraWidth);
        const height = Math.min(wanted.height, card.offsetHeight - extraHeight);
        const outerWidth = width + extraWidth;
        const outerHeight = height + extraHeight;
        return {
            x: Math.max(-RING, Math.min(wanted.x, card.offsetWidth + RING - outerWidth)),
            y: Math.max(-RING, Math.min(wanted.y, card.offsetHeight + RING - outerHeight)),
            width, height,
        };
    }

    function settle(label, wanted, broadcast = true) {
        const input = label.querySelector('textarea');
        const target = magnetTarget(label, wanted);
        mutedResize.set(input, Date.now() + ANIMATION_MS + 200);
        label.classList.add('mg-anim');
        input.classList.add('mg-anim');
        label.style.left = px(target.x);
        label.style.top = px(target.y);
        input.style.width = px(target.width);
        input.style.height = px(target.height);
        setTimeout(() => {
            label.classList.remove('mg-anim');
            input.classList.remove('mg-anim');
        }, ANIMATION_MS);
        if (broadcast) send({ type: 'label_position', owner_uid: label.dataset.uid, ...target });
    }

    document.addEventListener('mousedown', (event) => {
        if (event.button !== 0 || !event.target.closest('.mg-label-handle')) return;
        const label = event.target.closest('[data-drag="label"]');
        if (!label) return;
        event.preventDefault();
        label.classList.remove('mg-anim');
        label.querySelector('textarea').classList.remove('mg-anim');
        drag = { label, x: event.clientX, y: event.clientY,
                 left: coord(label, 'left'), top: coord(label, 'top') };
        label.classList.add('mg-dragging');
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (event) => {
        if (!drag) return;
        drag.label.style.left = px(drag.left + event.clientX - drag.x);
        drag.label.style.top = px(drag.top + event.clientY - drag.y);
    });

    function endDrag() {
        if (!drag) return;
        const label = drag.label;
        drag = null;
        label.classList.remove('mg-dragging');
        document.body.style.userSelect = '';
        settle(label);
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
            label.resizeTimer = setTimeout(() => settle(label), 300);
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
            settle(label, message, false);
        } else return;
        event.preventDefault();
    };

    for (const event of ['DOMContentLoaded', 'pageshow', 'htmx:historyRestore', 'htmx:afterSwap']) {
        document.addEventListener(event, watchLabels);
    }
})();
