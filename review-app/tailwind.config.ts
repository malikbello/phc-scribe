import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        sand: { 50: "#fbf9f5", 100: "#f6f2ea", 200: "#ece5d8", 300: "#dcd1bd" },
        ink: { DEFAULT: "#1d1b18", soft: "#57524a", faint: "#8a8378" },
        leaf: { 50: "#e9f5f0", 100: "#cfe9df", 500: "#2a8a70", 600: "#1f6f5c", 700: "#185748", 900: "#0e3129" },
        clay: { 50: "#fbeee9", 100: "#f5d5ca", 500: "#c4553b", 600: "#a8432d", 700: "#853423" },
        sun: { 100: "#fff1cc", 400: "#f2b53a", 600: "#b98010" },
        night: { 900: "#121311", 800: "#1a1c19", 700: "#242722", 600: "#30342e", 500: "#454a42" },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Noto Sans", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(29,27,24,.06), 0 4px 16px rgba(29,27,24,.06)",
        lift: "0 8px 30px rgba(29,27,24,.12)",
      },
      keyframes: {
        pop: { "0%": { transform: "scale(.9)", opacity: "0" }, "100%": { transform: "scale(1)", opacity: "1" } },
        rise: { "0%": { transform: "translateY(8px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        confetti: { "0%": { transform: "translateY(0) rotate(0)", opacity: "1" }, "100%": { transform: "translateY(120px) rotate(540deg)", opacity: "0" } },
      },
      animation: {
        pop: "pop .18s ease-out",
        rise: "rise .25s ease-out",
        confetti: "confetti 1.1s ease-in forwards",
      },
    },
  },
  plugins: [],
} satisfies Config;
