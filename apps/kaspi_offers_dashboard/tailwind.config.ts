import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0A0A0C',
          card: '#121214',
        },
        text: {
          primary: '#F5F5F7',
          secondary: '#A1A1AA',
        },
        primary: {
          DEFAULT: '#0A84FF',
          muted: '#64D2FF',
        },
        border: 'rgba(255,255,255,.06)'
      },
      boxShadow: {
        soft: '0 1px 2px rgba(0,0,0,.1), 0 8px 24px rgba(0,0,0,.2)'
      }
    },
  },
  plugins: [],
}

export default config


