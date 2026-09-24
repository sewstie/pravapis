// Applies the saved or system color theme before the page renders. Falls back to the system preference when storage is unavailable.
try {
  const saved = localStorage.getItem('pravapis-theme');
  document.documentElement.dataset.theme = saved === 'dark' || saved === 'light'
    ? saved : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
} catch {
  document.documentElement.dataset.theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
