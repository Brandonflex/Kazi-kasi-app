import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0a",
        surface: "#111111",
        "surface-light": "#1a1a1a",
        border: "#2a2a2a",
        "text-primary": "#f5f5f5",
        "text-secondary": "#a0a0a0",
        ember: "#ff6b35",
        "ember-gold": "#E9A23B",
        safari: "#2dd4a8",
        nairobi: "#1e90ff",
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        body: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
