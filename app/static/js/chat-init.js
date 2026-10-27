/* Boots the order chat widget on the thread page (kept separate to satisfy the CSP). */
(function () {
  "use strict";

  function boot() {
    var root = document.querySelector("[data-chat-root]");
    if (!root || !window.RC || !window.RC.initChat) return;

    var isAdmin = root.dataset.chatAdmin === "1";
    var empty = root.querySelector("[data-chat-empty]");

    window.RC.initChat({
      rootId: "rc-chat",
      chatId: parseInt(root.dataset.chatId, 10),
      isAdmin: isAdmin,
      pollUrl: root.dataset.pollUrl,
      markReadUrl: isAdmin ? null : root.dataset.readUrl,
      onStatus: function (payload) {
        if (empty) empty.remove();
        var badge = root.querySelector("[data-order-status]");
        if (badge && payload.label) {
          badge.textContent = payload.label[document.documentElement.lang] || payload.status;
        }
      }
    });

    var input = root.querySelector("[data-chat-input]");
    if (input) {
      input.addEventListener("input", function () {
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 128) + "px";
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
