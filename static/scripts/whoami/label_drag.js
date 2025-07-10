let draggedLabel = null;

function initLabel(element) {
    element.isClicked = false;
    element.isDragging = false;
}

function onLabelMouseDown(event) {
    const label = event.currentTarget;
    draggedLabel = label;
    if (label.isClicked) return;
    label.isClicked = true;

    const textarea = label.querySelector('textarea');
    if (event.target !== textarea) {
        label.isDragging = true;
        label.offsetX = event.clientX - label.offsetLeft;
        label.offsetY = event.clientY - label.offsetTop;
        document.body.style.userSelect = 'none';
    }
}

function onDocumentMouseMove(event) {
    if (draggedLabel && draggedLabel.isDragging) {
        draggedLabel.style.left = (event.clientX - draggedLabel.offsetX) + 'px';
        draggedLabel.style.top = (event.clientY - draggedLabel.offsetY) + 'px';
    }
}

function onDocumentMouseUp(ownerUID) {
    if (!draggedLabel) return;

    if (draggedLabel.isClicked) {
        draggedLabel.isDragging = false;
        document.body.style.userSelect = '';

        const pos = getStylePosition(draggedLabel);
        const scale = getStyleScale(draggedLabel);
        const transform = {...pos, ...scale};
        
        const params = getTransformParams(draggedLabel, draggedLabel.parentElement, transform);
        params.new.owner_uid = ownerUID;

        const triggerEl = htmx.findAll(draggedLabel, "div");
        console.log(triggerEl);
        if (triggerEl) {
            console.log({transform: params.new});
            htmx.trigger(triggerEl[triggerEl.length - 1], 'moved', { transform: params.new });
        }
        applyTransform(draggedLabel, params.old, params.new);
        draggedLabel.isClicked = false;
    }
    draggedLabel = null;
}

function onLabelWsMessage(event) {
    const el = event.currentTarget;
    if (!el.isDragging) {
        const params = getTransformParams(el, el.parentElement, event.detail);
        applyTransform(el, params.old, params.new);
    }
} 