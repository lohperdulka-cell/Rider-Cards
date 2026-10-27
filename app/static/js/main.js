/* RiderCards front-end behaviour: reveals, toasts, parallax, header, cart helpers. */
(function () {
  "use strict";

  const RC = (window.RC = window.RC || {});

  RC.csrf = function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  };

  /* ------------------------------------------------------- reveal on scroll */
  function initReveal(root) {
    const scope = root || document;
    const targets = scope.querySelectorAll("[data-reveal]:not(.is-visible)");
    if (!targets.length) return;
    if (!("IntersectionObserver" in window)) {
      targets.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    const observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    targets.forEach(function (el) { observer.observe(el); });
  }

  /* -------------------------------------------------------------- parallax */
  function initParallax() {
    const nodes = document.querySelectorAll("[data-parallax]");
    if (!nodes.length) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = null;
    const update = function () {
      const y = window.scrollY;
      nodes.forEach(function (el) {
        const speed = parseFloat(el.dataset.parallax || "0.15");
        el.style.transform = "translate3d(0," + (-y * speed).toFixed(2) + "px,0)";
      });
      frame = null;
    };
    window.addEventListener("scroll", function () {
      if (frame === null) frame = requestAnimationFrame(update);
    }, { passive: true });
    update();
  }

  /* -------------------------------------------------------------- counters */
  function initCounters() {
    const nodes = document.querySelectorAll("[data-count-to]");
    if (!nodes.length) return;
    const run = function (el) {
      const target = parseFloat(el.dataset.countTo || "0");
      const duration = 1200;
      const start = performance.now();
      const step = function (now) {
        const p = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString("ru-RU");
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    if (!("IntersectionObserver" in window)) {
      nodes.forEach(run);
      return;
    }
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { run(entry.target); observer.unobserve(entry.target); }
      });
    });
    nodes.forEach(function (el) { observer.observe(el); });
  }

  /* ---------------------------------------------------------------- toasts */
  const PALETTE = {
    success: "border-lime-brand/40 bg-lime-brand/12 text-lime-100",
    error: "border-rose-500/40 bg-rose-500/12 text-rose-100",
    info: "border-sky-400/40 bg-sky-400/12 text-sky-100",
    warning: "border-amber-400/40 bg-amber-400/12 text-amber-100"
  };

  RC.toast = function (message, category) {
    let host = document.getElementById("rc-toasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "rc-toasts";
      host.className = "pointer-events-none fixed bottom-5 right-5 z-[90] flex flex-col items-end gap-2";
      host.setAttribute("role", "status");
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = "rc-toast pointer-events-auto rc-card max-w-xs px-4 py-3 text-sm " +
      (PALETTE[category] || PALETTE.info);
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () {
      el.style.transition = "opacity .35s ease, transform .35s ease";
      el.style.opacity = "0";
      el.style.transform = "translateY(8px)";
      setTimeout(function () { el.remove(); }, 400);
    }, 4200);
  };

  function initServerFlashes() {
    const holder = document.getElementById("rc-flashes");
    if (!holder) return;
    try {
      JSON.parse(holder.textContent || "[]").forEach(function (item, index) {
        setTimeout(function () { RC.toast(item.message, item.category); }, index * 250);
      });
    } catch (err) { /* malformed payload must not break the page */ }
    holder.remove();
  }

  /* ----------------------------------------------------------- mobile menu */
  function initBurger() {
    const button = document.getElementById("rc-burger");
    const panel = document.getElementById("rc-mobile-menu");
    if (!button || !panel) return;
    const setOpen = function (open) {
      button.setAttribute("aria-expanded", open ? "true" : "false");
      panel.classList.toggle("hidden", !open);
      panel.classList.toggle("flex", open);
      document.documentElement.style.overflow = open ? "hidden" : "";
    };
    button.addEventListener("click", function () {
      setOpen(button.getAttribute("aria-expanded") !== "true");
    });
    panel.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { setOpen(false); });
    });
    panel.querySelectorAll("[data-burger-close]").forEach(function (el) {
      el.addEventListener("click", function () { setOpen(false); });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });
  }

  /* -------------------------------------------------------- sticky header */
  function initHeader() {
    const header = document.getElementById("rc-header");
    if (!header) return;
    const apply = function () {
      const scrolled = window.scrollY > 12;
      header.classList.toggle("bg-ink-950/85", scrolled);
      header.classList.toggle("border-white/10", scrolled);
      header.classList.toggle("border-transparent", !scrolled);
    };
    window.addEventListener("scroll", apply, { passive: true });
    apply();
  }

  /* --------------------------------------------------------- badges & cart */
  function swapBadge(name, value) {
    document.querySelectorAll('[data-badge="' + name + '"]').forEach(function (el) {
      el.textContent = value;
      el.classList.toggle("hidden", !value || value === "0");
    });
  }
  RC.bumpCart = function (count) { swapBadge("cart", String(count)); };
  RC.bumpWishlist = function (count) { swapBadge("wishlist", String(count)); };

  function postForm(url, payload) {
    const body = new URLSearchParams(payload).toString();
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRF-Token": RC.csrf(),
        "X-Requested-With": "fetch"
      },
      body: body
    }).then(function (response) {
      return response.json().catch(function () {
        return { ok: false, message: "Unexpected server response" };
      }).then(function (data) {
        return { ok: response.ok, status: response.status, data: data };
      });
    });
  }

  RC.addToCart = function (productId, qty) {
    return postForm("/cart/add", {
      product_id: productId,
      qty: qty || 1,
      csrf_token: RC.csrf()
    }).then(function (result) {
      const data = result.data || {};
      if (result.ok && data.ok) {
        RC.bumpCart(data.cart_count);
        RC.toast(data.message || "Товар в корзине", "success");
      } else {
        RC.toast(data.message || "Не удалось добавить товар", "error");
      }
      return data;
    });
  };

  RC.toggleWishlist = function (productId) {
    return postForm("/wishlist/toggle", {
      product_id: productId,
      csrf_token: RC.csrf()
    }).then(function (result) {
      const data = result.data || {};
      if (result.ok && data.ok) {
        RC.bumpWishlist(data.wishlist_count);
        RC.toast(data.message, data.added ? "success" : "info");
        document.querySelectorAll('[data-wishlist-toggle="' + productId + '"]').forEach(function (btn) {
          btn.setAttribute("aria-pressed", data.added ? "true" : "false");
        });
      } else {
        RC.toast(data.message || "Требуется вход", "error");
      }
      return data;
    });
  };

  /* ------------------------------------------------------------ cookie bar */
  function initCookieBar() {
    const bar = document.getElementById("rc-cookie-bar");
    if (!bar) return;
    if (localStorage.getItem("rc-cookie-consent") === "1") { bar.remove(); return; }
    bar.classList.remove("hidden");
    const accept = bar.querySelector("[data-cookie-accept]");
    if (accept) {
      accept.addEventListener("click", function () {
        localStorage.setItem("rc-cookie-consent", "1");
        bar.remove();
      });
    }
  }

  /* ---------------------------------------------------------------- gallery */
  function initGallery() {
    document.addEventListener("click", function (event) {
      const thumb = event.target.closest("[data-gallery-thumb]");
      if (!thumb) return;
      event.preventDefault();
      const root = thumb.closest("[data-gallery]");
      const stage = root && root.querySelector("[data-gallery-stage]");
      if (!stage) return;
      stage.src = thumb.dataset.galleryThumb;
      root.querySelectorAll("[data-gallery-thumb]").forEach(function (el) {
        el.classList.remove("ring-2", "ring-lime-brand");
      });
      thumb.classList.add("ring-2", "ring-lime-brand");
    });
  }

  /* ------------------------------------------------ progressive enhancement */
  function initForms() {
    document.addEventListener("submit", function (event) {
      const form = event.target;
      const confirmMessage = form.dataset.confirm;
      if (confirmMessage && !window.confirm(confirmMessage)) {
        event.preventDefault();
        return;
      }
      if (!form.matches("[data-add-to-cart]")) return;
      event.preventDefault();
      const qtyInput = form.querySelector("[name='qty']");
      RC.addToCart(form.dataset.productId, qtyInput ? qtyInput.value : 1);
    });
    document.addEventListener("click", function (event) {
      const button = event.target.closest("[data-wishlist-toggle]");
      if (!button) return;
      event.preventDefault();
      RC.toggleWishlist(button.dataset.wishlistToggle);
    });
  }

  /* ------------------------------------------------------ copy to clipboard */
  function initCopy() {
    document.addEventListener("click", function (event) {
      const trigger = event.target.closest("[data-copy]");
      if (!trigger) return;
      event.preventDefault();
      navigator.clipboard.writeText(trigger.dataset.copy).then(function () {
        RC.toast("Скопировано", "success");
      }).catch(function () {
        RC.toast("Не удалось скопировать", "error");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initReveal();
    initParallax();
    initCounters();
    initServerFlashes();
    initBurger();
    initHeader();
    initCookieBar();
    initCopy();
    initGallery();
    initForms();
  });

  document.addEventListener("htmx:afterSwap", function (event) { initReveal(event.target); });
  document.addEventListener("htmx:responseError", function () {
    RC.toast("Ошибка запроса, попробуйте снова", "error");
  });
})();
