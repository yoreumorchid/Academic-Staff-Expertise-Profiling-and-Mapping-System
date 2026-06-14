/**
 * Tailwind configuration encoding the Linear design system tokens
 * (DESIGN.md §2) in LIGHT MODE. Background surfaces use the
 * "Light Mode Neutrals" palette; brand and status colors are inherited
 * unchanged so the visual identity is preserved.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Background surfaces (LIGHT)
        bg: {
          marketing: "#f7f8f8",
          deepest: "#ffffff",
          panel: "#ffffff",
          surface: "#f5f6f7",
          secondary: "#eef0f2",
        },
        // Text (LIGHT — inverted hierarchy)
        text: {
          primary: "#0f1011",
          secondary: "#3d4148",
          tertiary: "#6b7079",
          quaternary: "#8a8f98",
        },
        // Brand & accent (slightly darkened violet for AA contrast on white)
        brand: {
          indigo: "#5e6ad2",
          violet: "#5b5fc7",
          hover: "#4d51b8",
          lavender: "#7a7fad",
          green: "#3b784b",
          "green-hover": "#2e6040",
        },
        // Status
        status: {
          green: "#1f8a37",
          emerald: "#10b981",
          red: "#d23f3f",
          amber: "#b6791b",
        },
        // Borders (LIGHT — soft cool greys)
        border: {
          primary: "#d0d6e0",
          secondary: "#e1e4ea",
          tertiary: "#edeff2",
          tint: "#f0f2f5",
          line: "#e6e8ec",
        },
      },
      borderRadius: {
        micro: "2px",
        std: "4px",
        comfy: "6px",
        card: "8px",
        panel: "12px",
        large: "22px",
      },
      fontFamily: {
        sans: [
          "Inter Variable",
          "SF Pro Display",
          "-apple-system",
          "system-ui",
          "Segoe UI",
          "Roboto",
          "Oxygen",
          "Ubuntu",
          "Cantarell",
          "Open Sans",
          "Helvetica Neue",
          "sans-serif",
        ],
        mono: ["Berkeley Mono", "ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
      fontWeight: {
        // Linear's signature in-between weights.
        signature: "510",
        announce: "590",
      },
      fontSize: {
        // Display sizes use aggressive negative tracking per DESIGN.md §3.
        "display-xl": ["4.5rem", { lineHeight: "1", letterSpacing: "-1.584px" }],
        "display-lg": ["4rem", { lineHeight: "1", letterSpacing: "-1.408px" }],
        display: ["3rem", { lineHeight: "1", letterSpacing: "-1.056px" }],
        "heading-1": ["2rem", { lineHeight: "1.13", letterSpacing: "-0.704px" }],
        "heading-2": ["1.5rem", { lineHeight: "1.33", letterSpacing: "-0.288px" }],
        "heading-3": ["1.25rem", { lineHeight: "1.33", letterSpacing: "-0.24px" }],
        "body-lg": ["1.125rem", { lineHeight: "1.6", letterSpacing: "-0.165px" }],
        body: ["1rem", { lineHeight: "1.5" }],
        small: ["0.9375rem", { lineHeight: "1.6", letterSpacing: "-0.165px" }],
        caption: ["0.8125rem", { lineHeight: "1.5", letterSpacing: "-0.13px" }],
        label: ["0.75rem", { lineHeight: "1.4" }],
      },
      // Light-mode shadow stack: soft, low-opacity drop shadows.
      boxShadow: {
        subtle: "0 1px 0 rgba(15,16,17,0.04)",
        ring: "0 0 0 1px rgba(15,16,17,0.06)",
        elevated:
          "0 1px 2px rgba(15,16,17,0.04), 0 4px 12px rgba(15,16,17,0.06)",
        floating:
          "0 1px 2px rgba(15,16,17,0.06), 0 8px 24px rgba(15,16,17,0.10)",
        dialog:
          "0 1px 2px rgba(15,16,17,0.06), 0 16px 48px rgba(15,16,17,0.18)",
        focus:
          "0 0 0 3px rgba(59,120,75,0.18), 0 1px 2px rgba(15,16,17,0.04)",
        inset: "inset 0 0 0 1px rgba(15,16,17,0.04)",
      },
    },
  },
  plugins: [],
};
