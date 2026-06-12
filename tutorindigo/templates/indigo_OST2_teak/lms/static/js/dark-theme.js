$(document).ready(function() {
    'use strict';

    const themeCookie = 'indigo-toggle-dark';

    // OST2: forward the current theme down to nested cross-origin iframes (e.g.
    // the r0x0r_arcade games embedded from ost2.fyi). CSS cannot cross an iframe
    // boundary and the games cannot read this domain's cookie, so each game
    // listens for a postMessage {'indigo-toggle-dark':'dark'|'light'} and toggles
    // its own .ost2-dark class (defaulting to light when no message arrives).
    // Sent on every applyThemeOnPage() (initial load + runtime toggle) and on
    // demand via the ost2GameThemeRequest handshake in the message listener.
    function broadcastThemeToChildIframes(themeVal){
      try {
        const frames = document.getElementsByTagName('iframe');
        for (let i = 0; i < frames.length; i++) {
          try {
            if (frames[i].contentWindow) {
              frames[i].contentWindow.postMessage({ 'indigo-toggle-dark': themeVal }, '*');
            }
          } catch (e) { /* cross-origin frame not ready yet; the handshake covers it */ }
        }
      } catch (e) { /* no-op */ }
    }

    function applyThemeOnPage(){
      const theme = $.cookie(themeCookie);
      {% if INDIGO_ENABLE_DARK_TOGGLE %}
      $('body').toggleClass("indigo-dark-theme", theme === 'dark');       // append or remove dark-class based on cookie-value
      // update expiry
      $.cookie(themeCookie, theme, { domain: window.location.hostname, expires: 90, path: '/' });
      broadcastThemeToChildIframes(theme === 'dark' ? 'dark' : 'light');  // OST2: keep embedded games in sync
      {% endif %}
      updateAccessibility();
    }

    function setThemeToggleBtnState(){
      const theme = $.cookie(themeCookie);
      $("#toggle-switch-input").prop("checked", theme === 'dark');
      updateAccessibility();
    }

    function updateAccessibility() {
      const theme = $.cookie(themeCookie);
      const textWrapper = $('#theme-label');
      if (theme === 'dark') {
        textWrapper.text('Switch to Light Mode');
        textWrapper.attr('aria-checked', 'true');
      } else {
        textWrapper.text('Switch to Dark Mode');
        textWrapper.attr('aria-checked', 'false');
      }
    }
    
    function toggleTheme(){
      const themeValue = $.cookie(themeCookie) === 'dark' ? 'light' : 'dark';
      $.cookie(themeCookie, themeValue, { domain: window.location.hostname, expires: 90, path: '/' });
        
      applyThemeOnPage();
    }

    // Listener for updating the theme inside an iframe
    window.addEventListener("message", function(e){
      if (e.data && e.data["indigo-toggle-dark"]){
        applyThemeOnPage();
      }
      // OST2: a nested game iframe asks for the current theme on its own load,
      // covering the race where the game mounts after applyThemeOnPage() already
      // broadcast. Reply directly to the requesting frame with 'dark'/'light'.
      if (e.data && e.data["ost2GameThemeRequest"] && e.source){
        const currentTheme = $.cookie(themeCookie) === 'dark' ? 'dark' : 'light';
        try { e.source.postMessage({ 'indigo-toggle-dark': currentTheme }, '*'); } catch (err) { /* no-op */ }
      }
    });

    applyThemeOnPage();  // loading theme on page load
    setThemeToggleBtnState(); // check/uncheck toggle btn based on theme

    $('#toggle-switch').on('change', toggleTheme);
    $('#toggle-switch-input').on('keydown', function (event) {
      if (event.key === "Enter") {
          toggleTheme();
      }
    });
});
