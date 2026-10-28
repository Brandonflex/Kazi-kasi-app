import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "#000000",
        surface: "#0a0a0a",
        "surface-elevated": "#111111",
        border: "#1f1f1f",
        "border-hover": "#2f2f2f",
        "text-primary": "#ededed",
        "text-secondary": "#a3a3a3",
        "text-muted": "#737373",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
