import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // text tones on the dark canvas
        sand: { 50: "#f7fbfa", 100: "#eaf4f1", 200: "#cfe0db", 300: "#a6bdb7" },
        ink: { DEFAULT: "#0a1114", soft: "#3c4f55", faint: "#6f8a95" },
        // primary: emerald (paired with cyan in gradients)
        leaf: { 50: "#e7fbf4", 100: "#b8f3dd", 400: "#3ee6a8", 500: "#22c993", 600: "#12a97c", 700: "#0b7f5d", 900: "#06372a" },
        // danger signs: coral
        clay: { 50: "#fff1f2", 100: "#ffd4d8", 400: "#ff8591", 500: "#f7596a", 600: "#e23d52", 700: "#b82a3e" },
        // caution / "needs change": amber
        sun: { 100: "#fff2cc", 400: "#ffc542", 600: "#d99a0b" },
        // canvas
        night: { 950: "#04080a", 900: "#070d10", 800: "#0c161b", 700: "#122029", 600: "#1b2d37", 500: "#6f8a95" },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Inter", "Noto Sans", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,.04) inset, 0 12px 40px -12px rgba(0,0,0,.55)",
        lift: "0 1px 0 rgba(255,255,255,.06) inset, 0 20px 60px -15px rgba(0,0,0,.7)",
        glow: "0 0 28px -6px rgba(62,230,168,.55)",
        "glow-coral": "0 0 26px -6px rgba(247,89,106,.6)",
      },
      keyframes: {
        pop: { "0%": { transform: "scale(.94)", opacity: "0" }, "100%": { transform: "scale(1)", opacity: "1" } },
        rise: { "0%": { transform: "translateY(10px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        confetti: { "0%": { transform: "translateY(0) rotate(0)", opacity: "1" }, "100%": { transform: "translateY(140px) rotate(540deg)", opacity: "0" } },
        drift: { "0%,100%": { transform: "translate(0,0) scale(1)" }, "50%": { transform: "translate(30px,-20px) scale(1.08)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        spinslow: { to: { transform: "rotate(360deg)" } },
      },
      animation: {
        pop: "pop .2s ease-out",
        rise: "rise .35s cubic-bezier(.2,.7,.2,1) both",
        confetti: "confetti 1.2s ease-in forwards",
        drift: "drift 18s ease-in-out infinite",
        shimmer: "shimmer 2.4s linear infinite",
        spinslow: "spinslow 9s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
