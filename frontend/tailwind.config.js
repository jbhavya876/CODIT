/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        chamber: {
          bg: '#0A0B0D',
          surface: '#15171B',
          elevated: '#1E2228',
          border: '#2A2E35',
          'border-subtle': '#1C1F24',
          text: '#F1F5F9',
          muted: '#8A94A6',
        },
        dossier: {
          bone: '#EFEAE0',
          surface: '#F7F4EE',
          elevated: '#FFFFFF',
          ink: '#101114',
          'ink-muted': '#575A65',
          border: '#D8D2C5',
          'border-subtle': '#E5DFD3',
        },
        laser: {
          lime: '#D4FF3A',
          'lime-dim': 'rgba(212, 255, 58, 0.12)',
          'lime-glow': 'rgba(212, 255, 58, 0.35)',
        },
        // Backward-compatible tokens mapped to Forensic Luxury palette
        codit: {
          bg: '#0A0B0D',
          bedrock: '#0A0B0D',
          surface: '#15171B',
          panel: '#15171B',
          elevated: '#1E2228',
          card: '#15171B',
          border: '#2A2E35',
          'border-bright': '#3D4450',
          'border-subtle': '#1C1F24',
          cyan: '#8CC8FF',
          emerald: '#5DE6A8',
          amber: '#FFB020',
          rose: '#FF4A2B',
          indigo: '#818cf8',
          text: {
            primary: '#F1F5F9',
            secondary: '#8A94A6',
            muted: '#525B6C',
          },
        },
        sev: {
          crit: {
            DEFAULT: '#FF4A2B',
            bg: '#2A0E0B',
            border: '#5A1C16',
          },
          high: {
            DEFAULT: '#FFB020',
            bg: '#281805',
            border: '#5E3808',
          },
          med: {
            DEFAULT: '#FACC15',
            bg: '#241F06',
            border: '#564908',
          },
          low: {
            DEFAULT: '#5DE6A8',
            bg: '#0B231A',
            border: '#164E37',
          },
          info: {
            DEFAULT: '#8CC8FF',
            bg: '#0C1B2E',
            border: '#1A3B66',
          },
        },
      },
      fontFamily: {
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['"Geist Sans"', 'Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'laser-glow': '0 0 20px -3px rgba(212, 255, 58, 0.35)',
        'verdict-glow': '0 0 50px -10px rgba(212, 255, 58, 0.25)',
        'crit-glow': '0 0 30px -5px rgba(255, 74, 43, 0.3)',
        'instrument': '0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.4)',
        'instrument-elevated': '0 8px 24px -4px rgba(0, 0, 0, 0.6)',
      },
    },
  },
  plugins: [],
}
