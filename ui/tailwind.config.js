/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Pretendard first: Tailwind's default ui-sans-serif/system-ui stack renders Korean
        // thin and tightly packed on this dark UI, which was flagged as hard to read.
        sans: ["Pretendard Variable", "Pretendard", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      keyframes: {
        // Red-alert flash: background and border swing between dim and bright red (week-9 review item).
        "alert-blink": {
          "0%, 100%": { backgroundColor: "rgb(69 10 10 / 0.7)", borderColor: "rgb(239 68 68)" },
          "50%": { backgroundColor: "rgb(127 29 29 / 0.95)", borderColor: "rgb(252 165 165)" },
        },
      },
      animation: {
        "alert-blink": "alert-blink 1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
