/** @type {import('tailwindcss').Config} */
/**
 * Tailwind v4 — la configuration thématique principale est portée par
 * `src/styles/tokens.css` via `@theme` (palette ink/bone/brass + accents
 * acte + typographie Cormorant/Inter/JetBrains Mono).
 * Ce fichier ne sert plus qu'à scoper les sources scannées par PostCSS.
 */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
}
