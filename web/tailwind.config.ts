import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // A single neutral ramp does almost all the work. Surfaces are
        // separated by fill lightness, never by borders.
        ink: {
          950: "#09090b",
          900: "#0c0c0e",
          850: "#101013",
          800: "#151519",
          700: "#1c1c21",
          600: "#26262c",
        },
        // Accent is used sparingly — status and one primary action.
        signal: {
          400: "#34d39e",
          500: "#1bbd86",
          600: "#0f9d6e",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        serif: ["var(--font-fraunces)", "Georgia", "Cambria", "Times New Roman", "serif"],
      },
      letterSpacing: {
        tightest: "-0.03em",
      },
      boxShadow: {
        // Borderless elevation: a hairline top highlight + a soft ambient drop.
        e1: "inset 0 1px 0 0 rgba(255,255,255,0.035), 0 1px 2px 0 rgba(0,0,0,0.4)",
        e2: "inset 0 1px 0 0 rgba(255,255,255,0.045), 0 8px 30px -16px rgba(0,0,0,0.7)",
      },
      keyframes: {
        breathe: {
          "0%, 100%": { opacity: "0.5" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        breathe: "breathe 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
