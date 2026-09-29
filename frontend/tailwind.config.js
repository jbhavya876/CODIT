/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        codit: {
          bg: '#080B11',
          bedrock: '#080B11',
          surface: '#0E1420',
          panel: '#0E1420',
          elevated: '#151E30',
          card: '#111827',
          border: '#1A2438',
          'border-bright': '#2A3B57',
          'border-subtle': '#131B2B',
          cyan: '#38bdf8',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#f43f5e',
          indigo: '#818cf8',
          text: {
            primary: '#E2E8F0',
            secondary: '#94A3B8',
            muted: '#475569',
          },
        },
        sev: {
          crit: {
            DEFAULT: '#F43F5E',
            bg: '#1E0A10',
            border: '#5C1220',
          },
          high: {
            DEFAULT: '#FB923C',
            bg: '#201205',
            border: '#5C2805',
          },
          med: {
            DEFAULT: '#FACC15',
            bg: '#1D1805',
            border: '#544405',
          },
          low: {
            DEFAULT: '#38BDF8',
            bg: '#071927',
            border: '#0C3852',
          },
          info: {
            DEFAULT: '#94A3B8',
            bg: '#111827',
            border: '#1E293B',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'instrument': '0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.4)',
        'instrument-elevated': '0 4px 12px 0 rgba(0, 0, 0, 0.5), 0 2px 4px -2px rgba(0, 0, 0, 0.4)',
      },
    },
  },
  plugins: [],
}
