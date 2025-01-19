function isJson(data) {
    try { JSON.parse(data) }
    catch (error) { return false }
    return true
}


function sendWSEvent(event) {
    let message = event.detail.message
    if (!isJson(message)) return
    message = JSON.parse(message)
    let container
    if (message.type === 'label_text') {
        container = htmx.find(`[data-label-text="${message.owner_uid}"]`)
    }
    else if (message.type === 'label_position') {
        container = htmx.find(`div[data-label="${message.owner_uid}"]`)
    }
    container.dispatchEvent(new CustomEvent('wsMessage', { detail: message }))
}