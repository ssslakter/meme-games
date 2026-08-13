/**
 * Who Am I board: cards move freely, each label rides along with its card.
 * Card positions are board-relative, label positions are card-relative, which is
 * what makes a label follow its card without the server touching it.
 */
(function () {
    const ANIM = 'mg-anim';
    const ANIM_MS = 500;
    /** How far outside its own card a label may be parked. Keeps a note in its owner's
     *  neighbourhood so nobody can drop one on top of somebody else's card. */
    const RING = 120;
    const TRAIL_PULL = 0.55, TRAIL_DECAY = 0.82, TRAIL_MAX = 70;

    let drag = null;
    const muteResize = new WeakMap();
    const lastSize = new WeakMap();

    const board = () => document.getElementById('players');
    const px = (v) => `${Math.round(v)}px`;
    const coord = (el, side) => parseInt(el.style[side], 10) || 0;
    const clamp = (v, min, max) => Math.max(min, Math.min(v, Math.max(min, max)));

    function send(msg) {
        const transport = document.getElementById('board-transport');
        if (!transport) return;
        window.mgBoardMsg = msg;
        htmx.trigger(transport, 'board-move');
    }

    /** The playfield minus whatever the floating lobby rail covers. */
    function bounds(area) {
        const rail = document.querySelector('.mg-lobby-tools');
        let width = area.clientWidth;
        if (rail && getComputedStyle(rail).position === 'fixed') {
            width = Math.min(width, rail.getBoundingClientRect().left - area.getBoundingClientRect().left - 12);
        }
        return { width: Math.max(width, 160), height: area.clientHeight };
    }

    /** A card is taller than its box: the notes pad hangs off the bottom and must stay in view. */
    function footprint(el) {
        const notes = el.querySelector(':scope > .mg-notes');
        return notes ? notes.offsetTop + notes.offsetHeight : el.offsetHeight;
    }

    function clampCard(card, x, y, area) {
        const box = bounds(area);
        return {
            x: clamp(x, 0, box.width - card.offsetWidth),
            y: clamp(y, 0, box.height - footprint(card)),
        };
    }

    /** Held inside a ring around its own card, and never pushed off the board. */
    function clampLabel(label, card, x, y, area) {
        const box = bounds(area);
        const cardX = coord(card, 'left'), cardY = coord(card, 'top');
        const w = label.offsetWidth, h = label.offsetHeight;
        x = clamp(x, -RING, card.offsetWidth + RING - w);
        y = clamp(y, -RING, footprint(card) + RING - h);
        return {
            x: clamp(cardX + x, 0, box.width - w) - cardX,
            y: clamp(cardY + y, 0, box.height - h) - cardY,
        };
    }

    function labelTransform(label) {
        const input = label.querySelector('textarea');
        return {
            x: coord(label, 'left'),
            y: coord(label, 'top'),
            width: input ? Math.round(input.offsetWidth) : 0,
            height: input ? Math.round(input.offsetHeight) : 0,
        };
    }

    function animate(el, apply) {
        const targets = [el, ...el.querySelectorAll('textarea')];
        targets.forEach((t) => t.classList.add(ANIM));
        apply();
        setTimeout(() => targets.forEach((t) => t.classList.remove(ANIM)), ANIM_MS);
    }

    /*----------------------------- trailing follow -----------------------------*/
    /* A card's note and pad are dragged along rather than welded on: they lag behind
       the card and settle back into their own relative spot once it stops. */

    const trailers = (card) => card.querySelectorAll(':scope > .mg-label, :scope > .mg-notes');

    function runTrail(card) {
        if (card.trailRaf) return;
        const step = () => {
            let moving = false;
            trailers(card).forEach((el) => {
                el.trailX = (el.trailX || 0) * TRAIL_DECAY;
                el.trailY = (el.trailY || 0) * TRAIL_DECAY;
                if (Math.abs(el.trailX) < 0.3 && Math.abs(el.trailY) < 0.3) el.trailX = el.trailY = 0;
                else moving = true;
                el.style.transform = el.trailX || el.trailY ? `translate(${el.trailX}px, ${el.trailY}px)` : '';
            });
            card.trailRaf = moving ? requestAnimationFrame(step) : null;
        };
        card.trailRaf = requestAnimationFrame(step);
    }

    function nudgeTrail(card, dx, dy) {
        trailers(card).forEach((el) => {
            el.trailX = clamp((el.trailX || 0) - dx * TRAIL_PULL, -TRAIL_MAX, TRAIL_MAX);
            el.trailY = clamp((el.trailY || 0) - dy * TRAIL_PULL, -TRAIL_MAX, TRAIL_MAX);
        });
        runTrail(card);
    }

    /*--------------------------------- dragging --------------------------------*/

    function dragTarget(event) {
        const label = event.target.closest('[data-drag="label"]');
        if (label) return event.target.closest('.mg-label-handle') ? { el: label, kind: 'label' } : null;
        if (event.target.closest('[data-nodrag], textarea, input, button, a')) return null;
        const card = event.target.closest('[data-drag="card"]');
        return card ? { el: card, kind: 'card' } : null;
    }

    document.addEventListener('mousedown', (event) => {
        if (event.button !== 0) return;
        const target = dragTarget(event);
        if (!target) return;
        event.preventDefault();
        drag = {
            ...target,
            pointerX: event.clientX, pointerY: event.clientY,
            lastX: event.clientX, lastY: event.clientY,
            originX: coord(target.el, 'left'), originY: coord(target.el, 'top'),
        };
        target.el.classList.remove(ANIM);
        target.el.classList.add('mg-dragging');
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (event) => {
        if (!drag) return;
        if (event.buttons === 0) return endDrag();  // mouseup happened off-window
        const area = board();
        if (!area) return;
        const { el, kind } = drag;
        const wanted = {
            x: drag.originX + (event.clientX - drag.pointerX),
            y: drag.originY + (event.clientY - drag.pointerY),
        };
        const next = kind === 'card'
            ? clampCard(el, wanted.x, wanted.y, area)
            : clampLabel(el, el.closest('[data-drag="card"]'), wanted.x, wanted.y, area);
        if (kind === 'card') nudgeTrail(el, next.x - coord(el, 'left'), next.y - coord(el, 'top'));
        el.style.left = px(next.x);
        el.style.top = px(next.y);
        drag.lastX = event.clientX;
        drag.lastY = event.clientY;
    });

    /** Always reachable: a mouseup the page never saw would otherwise freeze the board. */
    function endDrag() {
        if (!drag) return;
        const { el, kind } = drag;
        el.classList.remove('mg-dragging');
        document.body.style.userSelect = '';
        drag = null;
        if (kind === 'label') return send({ type: 'label_position', owner_uid: el.dataset.uid, ...labelTransform(el) });
        send({ type: 'card_position', owner_uid: el.dataset.uid, x: coord(el, 'left'), y: coord(el, 'top') });
        settleLabel(el);
    }

    document.addEventListener('mouseup', endDrag);
    window.addEventListener('blur', endDrag);

    /** A card that moved may have dragged its label past an edge; agree on the fix with everyone. */
    function settleLabel(card) {
        const area = board();
        const label = card.querySelector(':scope > [data-drag="label"]');
        if (!area || !label) return;
        const next = clampLabel(label, card, coord(label, 'left'), coord(label, 'top'), area);
        if (next.x === coord(label, 'left') && next.y === coord(label, 'top')) return;
        label.style.left = px(next.x);
        label.style.top = px(next.y);
        send({ type: 'label_position', owner_uid: label.dataset.uid, ...labelTransform(label) });
    }

    /** Positions are shared but screens are not: pull anything parked off this one back in. */
    function magnetIntoView() {
        const area = board();
        if (!area || drag) return;
        area.querySelectorAll(':scope > [data-drag="card"]').forEach((card) => {
            const at = clampCard(card, coord(card, 'left'), coord(card, 'top'), area);
            card.style.left = px(at.x);
            card.style.top = px(at.y);
            const label = card.querySelector(':scope > [data-drag="label"]');
            if (!label) return;
            const put = clampLabel(label, card, coord(label, 'left'), coord(label, 'top'), area);
            label.style.left = px(put.x);
            label.style.top = px(put.y);
        });
    }

    /*--------------------------------- resizing --------------------------------*/

    /** Labels are resized by the textarea's own grip, so watch it rather than the note. */
    const resizes = new ResizeObserver((entries) => {
        for (const entry of entries) {
            const input = entry.target;
            const label = input.closest('[data-drag="label"]');
            const size = `${Math.round(input.offsetWidth)}x${Math.round(input.offsetHeight)}`;
            const seen = lastSize.get(input);
            lastSize.set(input, size);
            if (!label || seen === undefined || seen === size) continue;
            if (Date.now() < (muteResize.get(input) || 0)) continue;
            clearTimeout(label.resizeTimer);
            label.resizeTimer = setTimeout(
                () => send({ type: 'label_position', owner_uid: label.dataset.uid, ...labelTransform(label) }), 300);
        }
    });

    function watchLabels() {
        document.querySelectorAll('[data-drag="label"] textarea').forEach((input) => resizes.observe(input));
        magnetIntoView();
    }

    /*------------------------------ remote updates -----------------------------*/

    function applyRemote(msg) {
        const area = board();
        if (msg.type === 'card_position') {
            const card = document.querySelector(`[data-card="${msg.owner_uid}"]`);
            if (!card || (drag && drag.el === card) || !area) return;
            const at = clampCard(card, msg.x, msg.y, area);
            nudgeTrail(card, at.x - coord(card, 'left'), at.y - coord(card, 'top'));
            animate(card, () => {
                card.style.left = px(at.x);
                card.style.top = px(at.y);
            });
        } else if (msg.type === 'label_position') {
            const label = document.querySelector(`[data-label="${msg.owner_uid}"]`);
            if (!label || (drag && drag.el === label) || !area) return;
            const input = label.querySelector('textarea');
            const at = clampLabel(label, label.closest('[data-drag="card"]'), msg.x, msg.y, area);
            animate(label, () => {
                label.style.left = px(at.x);
                label.style.top = px(at.y);
                if (!input || !msg.width || !msg.height) return;
                muteResize.set(input, Date.now() + ANIM_MS + 300);
                input.style.width = px(msg.width);
                input.style.height = px(msg.height);
            });
        } else if (msg.type === 'label_text') {
            const input = document.querySelector(`textarea[data-label-text="${msg.owner_uid}"]`);
            if (input && document.activeElement !== input) input.value = msg.label;
        } else {
            return false;
        }
        return true;
    }

    window.onBoardMessage = function (event) {
        const raw = event.detail.message;
        if (!isJson(raw)) return;
        const msg = JSON.parse(raw);
        if (msg && msg.type && applyRemote(msg)) event.preventDefault();
    };

    let resizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(magnetIntoView, 150);
    });

    for (const name of ['DOMContentLoaded', 'pageshow', 'htmx:historyRestore', 'htmx:afterSwap']) {
        document.addEventListener(name, watchLabels);
    }
})();
