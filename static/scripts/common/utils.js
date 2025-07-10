function isJson(data) {
    try { JSON.parse(data) }
    catch (error) { return false }
    return true
}
