/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        amd: {
          red: "#ED1C24",
          dark: "#0a0a0a",
          surface: "#111418",
          panel: "#1a1f26",
          border: "#2a323d",
          text: "#e6edf3",
          muted: "#8b949e",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
