/* Order chat widget: WebSocket first, JSON polling fallback. */
(function () {
  "use strict";

  const RC = (window.RC = window.RC || {});

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function bubble(message, isAdminView) {
    const own = isAdminView ? message.role === "admin" : message.role === "user";
    if (message.is_system || message.role === "system") {
      return '<div class="rc-bubble rc-bubble-system" data-message-id="' + message.id + '">' +
        escapeHtml(message.text) +
        '<span class="ml-2 opacity-60">' + escapeHtml(message.created_at) + "</span></div>";
    }
    const align = own ? "justify-end" : "justify-start";
    const cls = own ? "rc-bubble-user" : "rc-bubble-admin";
    const avatar = own ? "" :
      '<span class="rc-avatar mt-1" aria-hidden="true">' + escapeHtml(message.initials) + "</span>";
    return '<div class="flex ' + align + ' gap-2" data-message-id="' + message.id + '">' + avatar +
      '<div class="rc-bubble ' + cls + '">' +
      '<div class="mb-1 flex items-center gap-2 text-[11px] opacity-70"><span>' +
      escapeHtml(message.sender) + "</span><span>" + escapeHtml(message.created_at) + "</span></div>" +
      '<div class="whitespace-pre-wrap break-words">' + escapeHtml(message.text) + "</div></div></div>";
  }

  RC.initChat = function (options) {
    const root = document.getElementById(options.rootId);
    if (!root) return null;

    const chatId = options.chatId;
    const isAdminView = !!options.isAdmin;
    const stream = root.querySelector("[data-chat-stream]");
    const form = root.querySelector("[data-chat-form]");
    const input = root.querySelector("[data-chat-input]");
    const statusEl = root.querySelector("[data-chat-status]");
    const pollUrl = options.pollUrl;
    let socket = null;
    let pollTimer = null;
    let reconnectDelay = 1500;

    const scrollDown = function () {
      if (stream) stream.scrollTop = stream.scrollHeight;
    };

    const append = function (message) {
      if (!stream || !message) return;
      if (stream.querySelector('[data-message-id="' + message.id + '"]')) return;
      stream.insertAdjacentHTML("beforeend", bubble(message, isAdminView));
      scrollDown();
    };

    const setStatus = function (text, tone) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.className = "text-[11px] " +
        (tone === "live" ? "text-lime-brand" : tone === "off" ? "text-amber-300" : "text-white/45");
    };

    const startPolling = function () {
      if (pollTimer || !pollUrl) return;
      setStatus("Обновление каждые 3 с", "off");
      pollTimer = setInterval(function () {
        fetch(pollUrl, {
          credentials: "same-origin",
          headers: { "X-Requested-With": "fetch" }
        }).then(function (response) {
          return response.ok ? response.json() : null;
        }).then(function (data) {
          if (data && data.messages) data.messages.forEach(append);
        }).catch(function () { /* keep polling through transient errors */ });
      }, 3000);
    };

    const stopPolling = function () {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = null;
    };

    const connect = function () {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      try {
        socket = new WebSocket(scheme + "://" + window.location.host + "/ws/chat/" + chatId);
      } catch (err) {
        startPolling();
        return;
      }
      socket.addEventListener("open", function () {
        setStatus("Онлайн", "live");
        stopPolling();
        reconnectDelay = 1500;
      });
      socket.addEventListener("message", function (event) {
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch (err) {
          return;
        }
        if (payload.type === "history" && payload.messages) payload.messages.forEach(append);
        if (payload.type === "message") append(payload.message);
        if (payload.type === "status" && options.onStatus) options.onStatus(payload);
      });
      socket.addEventListener("close", function () {
        setStatus("Переподключение…", "off");
        startPolling();
        setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 15000);
      });
      socket.addEventListener("error", function () { startPolling(); });
    };

    const send = function (text) {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "message", text: text }));
        return true;
      }
      return false;
    };

    if (form && input) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        if (send(text)) return;
        const body = new URLSearchParams({ text: text, csrf_token: RC.csrf() }).toString();
        fetch(form.action, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRF-Token": RC.csrf(),
            "X-Requested-With": "fetch"
          },
          body: body
        }).then(function (response) { return response.json(); })
          .then(function (data) {
            if (data.message) append(data.message);
            else if (data.detail) RC.toast(data.detail, "error");
          })
          .catch(function () { RC.toast("Сообщение не отправлено", "error"); });
      });
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          form.requestSubmit();
        }
      });
    }

    scrollDown();
    connect();

    if (options.markReadUrl) {
      fetch(options.markReadUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": RC.csrf(), "X-Requested-With": "fetch" }
      }).catch(function () { /* read receipts are best effort */ });
    }

    return { append: append, send: send };
  };
})();
