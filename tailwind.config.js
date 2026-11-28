/** Tailwind ne garde que les classes trouvées dans ces fichiers : gabarits, scripts et la carte générée en Python. */
module.exports = {
  content: [
    "app/presentation/web/templates/**/*.html",
    "app/presentation/web/static/*.js",
    "app/infrastructure/opendata/*.py",
  ],
  theme: { extend: {} },
  plugins: [],
};
