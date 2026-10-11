/* Runs before first paint (plain script, not a module) so the page never flashes the wrong theme. */
(function () {
  var theme = null;
  try { theme = localStorage.getItem('lp_theme'); } catch (e) { /* storage blocked */ }
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', theme);
  var lang = null;
  try { lang = localStorage.getItem('lp_lang'); } catch (e) { /* storage blocked */ }
  document.documentElement.setAttribute('lang', lang === 'hi' ? 'hi' : 'en');
})();
