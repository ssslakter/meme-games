/**
 * Calculates the new coordinates and dimensions of the element within the parent container.
 * @param {HTMLElement} el - The element to be moved.
 * @param {HTMLElement} parent - The parent container element that acts as a boundary.
 * @param {{x: number, y: number}} transformData - An object with the target coordinates.
 * @returns {{new: object, old: object}} - An object with old and new parameters.
 */
function getTransformParams(el, parent, transformData) {
    const pRect = parent.getBoundingClientRect();
    const meRect = el.getBoundingClientRect();

    transformData.x = Math.max(0, Math.min(transformData.x, pRect.width - meRect.width));
    transformData.y = Math.max(0, Math.min(transformData.y, pRect.height - meRect.height));

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

    htmx.addClass(el, 'animated');

    if (old.x !== newParams.x || old.y !== newParams.y) {
        el.style.left = `${newParams.x}px`;
        el.style.top = `${newParams.y}px`;
    }

    const txt = htmx.find(el, 'textarea');
    if (txt && (old.width !== newParams.width || old.height !== newParams.height)) {
        txt.style.width = `${newParams.width}px`;
        txt.style.height = `${newParams.height}px`;
    }

    setTimeout(() => {
        htmx.removeClass(el, 'animated');
        if (txt) {
            txt.style.transition = 'none';
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
    const txt = htmx.find(el, 'textarea');
    if (!txt) return { width: 0, height: 0 };

    const txtStyles = window.getComputedStyle(txt);
    return {
        width: parseInt(txtStyles.width, 10),
        height: parseInt(txtStyles.height, 10)
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