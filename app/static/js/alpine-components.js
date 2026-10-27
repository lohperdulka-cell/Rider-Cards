/* Alpine.js (CSP build) components. Only property access and method calls are used,
   because the CSP build cannot evaluate inline expressions. */
document.addEventListener("alpine:init", () => {
  Alpine.data("dropdown", () => ({
    open: false,
    toggle() {
      this.open = !this.open;
    },
    close() {
      this.open = false;
    },
  }));

  Alpine.data("accordionItem", () => ({
    open: false,
    toggle() {
      this.open = !this.open;
    },
  }));

  Alpine.data("filters", () => ({
    open: false,
    toggle() {
      this.open = !this.open;
    },
  }));

  Alpine.data("quantity", () => ({
    value: 1,
    max: 99,
    init() {
      this.value = parseInt(this.$el.dataset.initial || "1", 10) || 1;
      this.max = parseInt(this.$el.dataset.max || "99", 10) || 99;
    },
    increment() {
      if (this.value < this.max) this.value += 1;
    },
    decrement() {
      if (this.value > 1) this.value -= 1;
    },
    sync(event) {
      const parsed = parseInt(event.target.value, 10);
      this.value = isNaN(parsed) ? 1 : Math.min(Math.max(parsed, 1), this.max);
    },
  }));

  Alpine.data("gallery", () => ({
    active: 0,
    images: [],
    init() {
      try {
        this.images = JSON.parse(this.$el.dataset.images || "[]");
      } catch (err) {
        this.images = [];
      }
    },
    select(index) {
      this.active = index;
      const img = this.$refs.stage;
      if (img) img.src = this.images[this.active] || img.src;
    },
    next() {
      this.select((this.active + 1) % Math.max(1, this.images.length));
    },
    prev() {
      this.select((this.active - 1 + this.images.length) % Math.max(1, this.images.length));
    },
  }));

  Alpine.data("toasts", () => ({
    items: [],
    push(message, category) {
      this.items.push({ message: message, category: category || "info", id: Date.now() });
      const id = this.items[this.items.length - 1].id;
      setTimeout(() => this.dismiss(id), 4200);
    },
    dismiss(id) {
      this.items = this.items.filter((item) => item.id !== id);
    },
  }));
});
