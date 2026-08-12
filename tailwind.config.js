/** @type {import('tailwindcss').Config} */
module.exports = {
  // Antes el sitio usaba el CDN de cdn.tailwindcss.com en produccion -- si
  // ese CDN externo se caia (paso de verdad, connection timed out), TODO el
  // estilo del sitio se rompia de golpe porque no habia ningun CSS propio
  // de respaldo. Este config compila un CSS propio, servido como static
  // file (sin depender de ningun servicio externo en producción).
  content: [
    './templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        brand: { 50: '#F7F4FC', 100: '#EDE7F7', 200: '#DCD1EE', 400: '#9C82C9', 500: '#7A5AB4', 600: '#6A4DA3', 700: '#5E4694', 900: '#2E2447' },
        accent: { 50: '#E9F5F5', 100: '#D2ECEC', 500: '#168486', 700: '#0F6B6D' },
        surface: '#FAFAFC',
      },
    },
  },
  plugins: [],
}
