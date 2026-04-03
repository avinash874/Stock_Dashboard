/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "#0f1419",
        card: "#151b24",
        line: "#2d3a4d",
        muted: "#8b9bb4",
        accent: "#3d9eff",
        mint: "#5ce1c5",
        gold: "#c9a227",
        danger: "#e07a5f",
      },
    },
  },
  plugins: [],
};
