function isJson(data) {
    try { JSON.parse(data) }
    catch (error) { return false }
    return true
}

function hideDropdowns() {
    for (const dropdown of document.querySelectorAll('[uk-dropdown]')) {
        UIkit.dropdown(dropdown).hide();
        dropdown.classList.remove('uk-open'); 
        // force remove class if UIkit.hide() doesn't work
    }
}