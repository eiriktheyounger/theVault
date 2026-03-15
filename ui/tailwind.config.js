/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx,js,jsx,html,md,mdx}',
    // keep any additional paths from the current config
  ],
  theme: {
    extend: {
      colors: {
        brand: 'var(--brand)',
        bg: 'var(--bg)',
        panel: 'var(--panel)',
        panel2: 'var(--panel2)',
        border: 'var(--border)',
        text: 'var(--text)',
        muted: 'var(--muted)',
        info: '#22D3EE',
        success: '#22C55E',
        warn: '#EAB308',
        error: '#EF4444',
      },
      boxShadow: { soft: '0 6px 24px rgba(0,0,0,0.35)' },
      borderRadius: { '2xl': '1rem' },
      typography: ({ theme }) => ({
        DEFAULT: {
          css: {
            color: theme('colors.text'),
            a: { color: theme('colors.brand') },
            h1: { color: theme('colors.text') },
            h2: { color: theme('colors.text') },
            h3: { color: theme('colors.text') },
            code: { color: theme('colors.info') },
            'code::before': { content: 'none' },
            'code::after': { content: 'none' },
          },
        },
        invert: {
          css: { color: theme('colors.text') },
        },
      }),
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
    // optional:
    // require('@tailwindcss/line-clamp'),
    // require('@tailwindcss/container-queries'),
  ],
};
