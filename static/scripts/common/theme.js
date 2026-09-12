function setThemeMode(dark) {
  const mode = dark ? 'dark' : 'light';
  const franken = JSON.parse(localStorage.getItem('__FRANKEN__') || '{}');
  franken.mode = mode;
  localStorage.setItem('__FRANKEN__', JSON.stringify(franken));
}

function toggleThemeMode() {
  const dark = !document.documentElement.classList.contains('dark');
  document.documentElement.classList.toggle('dark', dark);
  setThemeMode(dark);
}
