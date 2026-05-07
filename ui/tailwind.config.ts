import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "system-ui", "sans-serif"],
        display: ["Noto Serif SC", "Songti SC", "STSong", "SimSun", "serif"],
        mono: ["JetBrains Mono", "Menlo", "Consolas", "monospace"],
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
