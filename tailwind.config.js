/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#050506",
          900: "#0a0a0c",
          850: "#101014",
          800: "#16161b",
          700: "#1f1f26",
          600: "#2b2b34",
          500: "#3a3a45",
        },
        lime: {
          brand: "#A3E635",
          deep: "#84CC16",
          dark: "#4d7c0f",
        },
      },
      fontFamily: {
        display: ['"Bebas Neue"', '"Oswald"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(163,230,53,.35), 0 18px 60px -20px rgba(163,230,53,.55)",
        card: "0 24px 60px -32px rgba(0,0,0,.9)",
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(to bottom, rgba(163,230,53,.06), transparent 70%)",
      },
      keyframes: {
        floaty: {
          "0%,100%": { transform: "translateY(0) rotate(0deg)" },
          "50%": { transform: "translateY(-14px) rotate(3deg)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgba(163,230,53,.5)" },
          "70%": { boxShadow: "0 0 0 12px rgba(163,230,53,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(163,230,53,0)" },
        },
      },
      animation: {
        floaty: "floaty 7s ease-in-out infinite",
        shimmer: "shimmer 2.2s infinite",
        "pulse-ring": "pulseRing 2s infinite",
      },
      transitionTimingFunction: {
        brand: "cubic-bezier(.22,.61,.36,1)",
      },
    },
  },
  plugins: [],
};
