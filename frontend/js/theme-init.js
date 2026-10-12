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
  document.documentElement.setAttribute('lang', /^(hi|bn|mr|te|ta)$/.test(lang || '') ? lang : 'en');
})();

/* Safety net: if the app's scripts fail to start (for example a stale copy
   cached by the browser), show a way out instead of an empty page. */
(function () {
  function showFallback() {
    var main = document.getElementById('content');
    if (!main || main.children.length) return;
    main.innerHTML = '<div style="max-width:520px;margin:12vh auto;padding:28px;border-radius:20px;background:rgba(127,127,127,.12);font-family:system-ui,sans-serif;line-height:1.5">'
      + '<h1 style="margin:0 0 8px;font-size:1.4rem">LifePilot could not start</h1>'
      + '<p style="margin:0 0 16px">Your browser may be using an old copy of the app. Reloading usually fixes it.</p>'
      + '<button type="button" id="lpReload" style="font:inherit;font-weight:600;padding:10px 18px;border-radius:999px;border:0;background:#ff7a1a;color:#121a2f;cursor:pointer">Reload LifePilot</button></div>';
    document.getElementById('lpReload').addEventListener('click', function () { location.reload(); });
  }
  window.addEventListener('error', function (e) {
    var t = e.target;
    var scriptFailed = (typeof ErrorEvent !== 'undefined' && e instanceof ErrorEvent) || (t && t.tagName === 'SCRIPT');
    if (scriptFailed) setTimeout(showFallback, 0);
  }, true);
})();
