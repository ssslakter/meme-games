let draggedElement = null;
let offsetX, offsetY;

function makeDraggable(element) {
    if (!element) return;

    element.style.cursor = 'move';

    element.addEventListener('mousedown', (e) => {
        const clickedTextarea = e.target.closest('textarea');

        if (clickedTextarea && clickedTextarea === element.querySelector('textarea')) {
            return;
        }

        e.preventDefault();

        draggedElement = element;

        const initialRect = draggedElement.getBoundingClientRect();

        draggedElement.classList.remove('-translate-x-1/2', '-translate-y-1/2');

        draggedElement.style.left = initialRect.left + 'px';
        draggedElement.style.top = initialRect.top + 'px';

        offsetX = e.clientX - initialRect.left;
        offsetY = e.clientY - initialRect.top;

        element.style.cursor = 'grabbing';

        document.body.style.userSelect = 'none';
        draggedElement.style.zIndex = '9999';

        const textarea = draggedElement.querySelector('textarea');
        if (textarea) {
            textarea.style.pointerEvents = 'none';
        }
    });
}

document.addEventListener('mousemove', (e) => {
    if (draggedElement) {
        e.preventDefault();
        draggedElement.style.left = (e.clientX - offsetX) + 'px';
        draggedElement.style.top = (e.clientY - offsetY) + 'px';
    }
});

document.addEventListener('mouseup', () => {
    if (draggedElement) {
        draggedElement.style.cursor = 'grab';
        
        draggedElement.style.zIndex = '';

        const textarea = draggedElement.querySelector('textarea');
        if (textarea) {
            textarea.style.pointerEvents = '';
        }

        draggedElement = null;

        document.body.style.userSelect = '';
    }
});

document.addEventListener('selectstart', (e) => {
    if (draggedElement) {
        e.preventDefault();
    }
});

function initializeDraggables() {
    document.querySelectorAll('.draggable-panel').forEach(makeDraggable);
}
let events = ['DOMContentLoaded', 'pageshow', 'htmx:historyRestore', 'htmx:afterSwap'];
for (let event of events) {
    document.addEventListener(event, initializeDraggables);
}
