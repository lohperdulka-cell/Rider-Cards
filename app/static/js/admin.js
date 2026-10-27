/* Admin dashboard: charts and bulk-selection helpers. */
(function () {
  "use strict";

  const RC = (window.RC = window.RC || {});

  RC.initDashboardChart = function (canvasId, payloadId) {
    const canvas = document.getElementById(canvasId);
    const payload = document.getElementById(payloadId);
    if (!canvas || !payload || typeof Chart === "undefined") return;

    let series = [];
    try {
      series = JSON.parse(payload.textContent || "[]");
    } catch (err) {
      return;
    }

    const styles = getComputedStyle(document.documentElement);
    const lime = styles.getPropertyValue("--rc-lime").trim() || "#A3E635";
    const limeDeep = styles.getPropertyValue("--rc-lime-deep").trim() || "#84CC16";
    const context = canvas.getContext("2d");
    const gradient = context.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, "rgba(163,230,53,.55)");
    gradient.addColorStop(1, "rgba(163,230,53,0)");

    new Chart(context, {
      type: "line",
      data: {
        labels: series.map(function (item) { return item.label; }),
        datasets: [
          {
            label: "Заказы",
            data: series.map(function (item) { return item.orders; }),
            borderColor: lime,
            backgroundColor: gradient,
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 0,
            yAxisID: "y"
          },
          {
            label: "Выручка, ₽",
            data: series.map(function (item) { return item.revenue; }),
            borderColor: limeDeep,
            borderDash: [6, 4],
            borderWidth: 2,
            tension: 0.35,
            pointRadius: 0,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "rgba(255,255,255,.65)", boxWidth: 12 } },
          tooltip: {
            backgroundColor: "rgba(10,10,12,.92)",
            borderColor: "rgba(163,230,53,.35)",
            borderWidth: 1
          }
        },
        scales: {
          x: {
            ticks: { color: "rgba(255,255,255,.45)" },
            grid: { color: "rgba(255,255,255,.05)" }
          },
          y: {
            position: "left",
            ticks: { color: "rgba(255,255,255,.45)", precision: 0 },
            grid: { color: "rgba(255,255,255,.05)" }
          },
          y1: {
            position: "right",
            ticks: { color: "rgba(255,255,255,.45)" },
            grid: { display: false }
          }
        }
      }
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    const master = document.querySelector("[data-check-master]");
    if (!master) return;
    master.addEventListener("change", function () {
      const group = master.dataset.checkGroup;
      document.querySelectorAll('[data-check-group="' + group + '"]').forEach(function (box) {
        box.checked = master.checked;
      });
    });
  });
})();
