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
// Chat lines are stamped with the server's clock; the reader is not always in that
// zone. Runs after swaps too - lines arrive one at a time over the websocket.
function localTimes() {
    for (const el of document.querySelectorAll('time.mg-chat-time[datetime]')) {
        const at = new Date(el.dateTime);
        if (isNaN(at)) continue;
        // 24h regardless of locale: it matches the server-rendered fallback, so the
        // stamp does not visibly reshuffle on load, and it stays five characters wide
        el.textContent = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        el.title = at.toLocaleString();
    }
}

for (const event of ['DOMContentLoaded', 'htmx:afterSwap', 'htmx:oobAfterSwap']) {
    document.addEventListener(event, localTimes);
}
