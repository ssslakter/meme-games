let draggedLabel = null;

function initLabel(element) {
    element.isClicked = false;
    element.isDragging = false;
}

function getCorrectedTextareaDimensions(labelEl, textareaEl, newParams) {
    const deltaWidth = labelEl.offsetWidth - textareaEl.offsetWidth;
    const deltaHeight = labelEl.offsetHeight - textareaEl.offsetHeight;
    return {
        width: newParams.width - deltaWidth,
        height: newParams.height - deltaHeight
    };
}

function onLabelMouseDown(event) {
    const label = event.currentTarget;
    label.style.cursor = 'grabbing';
    draggedLabel = label;
    if (label.isClicked) return;
    label.isClicked = true;

    const classes = 'transition-all duration-500 ease-in-out';
    for (const cls of classes.split(' ')) {
        htmx.removeClass(label, cls);
        const txt = htmx.find(label, 'textarea');
        if (txt) htmx.removeClass(txt, cls);
    }

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

function onDocumentMouseUp(event) {
    if (!draggedLabel) return;
    draggedLabel.style.cursor = 'grab';
    let ownerUID = htmx.find(draggedLabel.parentElement, 'div[data-label]').getAttribute('data-label');
    if (draggedLabel.isClicked) {
        draggedLabel.isDragging = false;
        document.body.style.userSelect = '';

        const pos = getStylePosition(draggedLabel);
        const scale = getStyleScale(draggedLabel);
        const transform = {...pos, ...scale};
        
        const params = getTransformParams(draggedLabel, draggedLabel.parentElement, transform);
        params.new.owner_uid = ownerUID;

        const textarea = draggedLabel.querySelector('textarea');
        const deltaWidth = draggedLabel.offsetWidth - textarea.offsetWidth;
        const deltaHeight = draggedLabel.offsetHeight - textarea.offsetHeight;
        if (textarea) {
            params.new.width = params.new.width - deltaWidth;
            params.new.height = params.new.height - deltaHeight;
        }

        const triggerEl = htmx.findAll(draggedLabel, "div");
        if (triggerEl) {
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