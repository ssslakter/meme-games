(function () {
  const key = 'meme-games.allow-agents';
  document.addEventListener('click', function (event) {
    const link = event.target.closest('a[data-new-lobby="true"], a.mg-game-link');
    if (!link || localStorage.getItem(key) === null) return;
    const url = new URL(link.href, location.href);
    url.searchParams.set('allow_agents', localStorage.getItem(key) === 'true' ? '1' : '0');
    link.href = url.toString();
  }, true);
}());
