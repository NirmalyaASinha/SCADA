/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0a0a0a',
        'bg-panel': '#111111',
        'bg-card': '#1a1a1a',
        'bg-hover': '#222222',
        'border': '#2a2a2a',
        'text-primary': '#e8e8e8',
        'text-secondary': '#888888',
        'status-green': '#00ff88',
        'status-amber': '#ffaa00',
        'status-red': '#ff3333',
        'status-blue': '#0088ff',
        'status-purple': '#aa44ff',
        'dim-green': '#004422',
        'dim-amber': '#442200',
        'dim-red': '#440000',
        'dim-purple': '#220044',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
