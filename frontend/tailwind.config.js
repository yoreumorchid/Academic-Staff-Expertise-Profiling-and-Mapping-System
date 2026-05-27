/**
 * Tailwind configuration encoding the Linear design system tokens
 * defined in DESIGN.md. Every color, radius, shadow, and font-size used
 * across the application must trace back to one of these tokens —
 * arbitrary inline values are prohibited per instructions.md §5.2.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Background surfaces
        bg: {
          marketing: "#08090a",
          deepest: "#010102",
          panel: "#0f1011",
          surface: "#191a1b",
          secondary: "#28282c",
        },
        // Text
        text: {
          primary: "#f7f8f8",
          secondary: "#d0d6e0",
          tertiary: "#8a8f98",
          quaternary: "#62666d",
        },
        // Brand & accent
        brand: {
          indigo: "#5e6ad2",
          violet: "#7170ff",
          hover: "#828fff",
          lavender: "#7a7fad",
        },
        // Status
        status: {
          green: "#27a644",
          emerald: "#10b981",
        },
        // Borders (solid variants)
        border: {
          primary: "#23252a",
          secondary: "#34343a",
          tertiary: "#3e3e44",
          tint: "#141516",
          line: "#18191a",
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
      boxShadow: {
        subtle: "rgba(0,0,0,0.03) 0px 1.2px 0px 0px",
        ring: "rgba(0,0,0,0.2) 0px 0px 0px 1px",
        elevated: "rgba(0,0,0,0.4) 0px 2px 4px",
        dialog:
          "rgba(0,0,0,0) 0px 8px 2px, rgba(0,0,0,0.01) 0px 5px 2px, rgba(0,0,0,0.04) 0px 3px 2px, rgba(0,0,0,0.07) 0px 1px 1px, rgba(0,0,0,0.08) 0px 0px 1px",
        focus: "rgba(0,0,0,0.1) 0px 4px 12px",
        inset: "rgba(0,0,0,0.2) 0px 0px 12px 0px inset",
      },
    },
  },
  plugins: [],
};
