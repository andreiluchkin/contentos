import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Jitter дизайн-система
        canvas: "#f2f1f3",
        card: "#ffffff",
        ink: "#19171c",
        "ink-secondary": "#6b6870",
        accent: "#7a40ed",
        "accent-light": "#ede8fb",
        blue: "#00b2ff",
        volt: "#f5ff63",
        border: "#e8e6eb",
        "border-strong": "#d4d1d9",
      },
      borderRadius: {
        button: "50px",
        card: "40px",
        badge: "40px",
        input: "26px",
        nav: "20px",
        sm: "12px",
      },
      fontFamily: {
        display: ["TWK Lausanne", "Inter Tight", "system-ui", "sans-serif"],
        ui: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(25,23,28,0.06), 0 4px 12px rgba(25,23,28,0.04), 0 16px 40px rgba(25,23,28,0.03), 0 40px 80px rgba(25,23,28,0.02)",
        "card-hover": "0 2px 6px rgba(25,23,28,0.08), 0 8px 24px rgba(25,23,28,0.06), 0 24px 60px rgba(25,23,28,0.05), 0 60px 120px rgba(25,23,28,0.03)",
        button: "0 1px 2px rgba(25,23,28,0.08), 0 4px 12px rgba(122,64,237,0.2)",
      },
      animation: {
        "fade-in": "fadeIn 150ms ease-out",
        "slide-up": "slideUp 200ms ease-out",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
}

export default config
