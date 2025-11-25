/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#2563eb',
          blue: '#2563eb',
        },
        'pm-primary': '#2563eb',
        'pm-secondary': '#1d4ed8',
        success: {
          DEFAULT: '#10b981',
          green: '#10b981',
        },
        error: {
          DEFAULT: '#ef4444',
          red: '#ef4444',
        },
        warning: {
          DEFAULT: '#f59e0b',
          orange: '#f59e0b',
        },
      },
    },
  },
  plugins: [],
}
