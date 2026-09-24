// Apply the preference before the first paint; storage can be unavailable.
try {
  const saved = localStorage.getItem('pravapis-theme');
  document.documentElement.dataset.theme = saved === 'dark' || saved === 'light'
    ? saved : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
} catch {
  document.documentElement.dataset.theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
