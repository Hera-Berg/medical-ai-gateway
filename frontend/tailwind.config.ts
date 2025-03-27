import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['var(--font-display)', 'Georgia', 'serif'],
        body: ['var(--font-body)', 'system-ui', 'sans-serif'],
      },
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        border: 'var(--border)',
        'border-strong': 'var(--border-strong)',
        ink: 'var(--ink)',
        'ink-soft': 'var(--ink-soft)',
        'ink-mute': 'var(--ink-mute)',
        brand: 'var(--brand)',
        'brand-soft': 'var(--brand-soft)',
        'brand-ink': 'var(--brand-ink)',
        authoritative: 'var(--authoritative)',
        'authoritative-soft': 'var(--authoritative-soft)',
        'authoritative-ink': 'var(--authoritative-ink)',
        personal: 'var(--personal)',
        'personal-soft': 'var(--personal-soft)',
        'personal-ink': 'var(--personal-ink)',
        ok: 'var(--ok)',
        warn: 'var(--warn)',
        'warn-soft': 'var(--warn-soft)',
        danger: 'var(--danger)',
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        sm: 'var(--radius-sm)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
      },
    },
  },
  plugins: [],
};
export default config;
