import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Inter", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: {
          DEFAULT: "oklch(20% 0.01 250)",
          muted: "oklch(45% 0.01 250)",
          subtle: "oklch(60% 0.01 250)",
        },
        canvas: {
          DEFAULT: "oklch(99% 0 0)",
          soft: "oklch(97% 0.005 250)",
          card: "oklch(100% 0 0)",
        },
        accent: {
          DEFAULT: "oklch(55% 0.18 250)",
          fg: "oklch(98% 0 0)",
        },
        warn: {
          DEFAULT: "oklch(72% 0.18 60)",
          soft: "oklch(95% 0.06 80)",
          ink: "oklch(35% 0.12 50)",
        },
        ok: {
          DEFAULT: "oklch(72% 0.15 160)",
          soft: "oklch(95% 0.05 160)",
          ink: "oklch(30% 0.1 165)",
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 8px 24px -12px rgb(0 0 0 / 0.08)",
        ring: "inset 0 0 0 1px oklch(90% 0.005 250)",
      },
    },
  },
  plugins: [],
};

export default config;
