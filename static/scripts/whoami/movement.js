/**
 * Calculates the new coordinates and dimensions of the element within the parent container.
 * @param {HTMLElement} el - The element to be moved.
 * @param {HTMLElement} parent - The parent container element that acts as a boundary.
 * @param {{x: number, y: number}} transformData - An object with the target coordinates.
 * @returns {{new: object, old: object}} - An object with old and new parameters.
 */
function getTransformParams(el, parent, transformData) {
    const pRect = parent.getBoundingClientRect();

    let newX = transformData.x;
    let newY = transformData.y;
    let newW = transformData.width;
    let newH = transformData.height;

    newW = Math.min(newW, pRect.width);
    newH = Math.min(newH, pRect.height);

    newX = Math.max(0, Math.min(newX, pRect.width - newW));
    newY = Math.max(0, Math.min(newY, pRect.height - newH));

    transformData.x = newX;
    transformData.y = newY;
    transformData.width = newW;
    transformData.height = newH;

    const curPos = getStylePosition(el);
    const currScale = getStyleScale(el);

    return {
        new: transformData,
        old: { ...curPos, ...currScale }
    };
}

/**
 * Applies a transformation to the element: changes its position and size.
 * @param {HTMLElement} el - The element to transform.
 * @param {object} old - The old parameters {x, y, width, height}.
 * @param {object} newParams - The new parameters {x, y, width, height}.
 */
function applyTransform(el, old, newParams) {
    if (newParams.x === old.x && newParams.y === old.y && old.width === newParams.width && old.height === newParams.height) {
        el.isClicked = false;
        return;
    }

    const classes = 'transition-all duration-500 ease-in-out';
    const txt = htmx.find(el, 'textarea');

    for (const cls of classes.split(' ')) {
        htmx.addClass(el, cls);
        if (txt) htmx.addClass(txt, cls);
    }

    if (old.x !== newParams.x || old.y !== newParams.y) {
        el.style.left = `${newParams.x}px`;
        el.style.top = `${newParams.y}px`;
    }

    if (txt && (old.width !== newParams.width || old.height !== newParams.height)) {
        const deltaWidth = el.offsetWidth - txt.offsetWidth;
        const deltaHeight = el.offsetHeight - txt.offsetHeight;
        txt.style.width = `${newParams.width - deltaWidth}px`;
        txt.style.height = `${newParams.height - deltaHeight}px`;
    }

    setTimeout(() => {
        for (const cls of classes.split(' ')) {
            htmx.removeClass(el, cls);
            if (txt) htmx.removeClass(txt, cls);
        }
        el.isClicked = false;
    }, 500);
}

/**
 * Gets the current dimensions (width and height) of the textarea nested within the element.
 * @param {HTMLElement} el - The parent element.
 * @returns {{width: number, height: number}}
 */
function getStyleScale(el) {
    const elStyles = window.getComputedStyle(el);
    return {
        width: parseInt(elStyles.width, 10),
        height: parseInt(elStyles.height, 10)
    };
}

/**
 * Gets the current coordinates (left, top) of an element from its styles.
 * @param {HTMLElement} el - The element.
 * @returns {{x: number, y: number}}
 */
function getStylePosition(el) {
    const style = window.getComputedStyle(el);
    return {
        x: parseInt(style.left, 10),
        y: parseInt(style.top, 10)
    };
}