/* Admin dashboard chart boot (separate file so the CSP needs no inline script). */
(function () {
  "use strict";

  function boot() {
    if (window.RC && window.RC.initDashboardChart) {
      window.RC.initDashboardChart("rc-admin-chart", "rc-admin-series");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
