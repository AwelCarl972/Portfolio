# Image du portfolio : construite sur le poste, puis chargée sur le serveur (docker save | docker load).
# Le serveur n'a donc besoin ni de Rust ni de RAM pour compiler — il est partagé avec LTE et MGE.

# --- 1. Le binaire Rust (profilage qualité, pseudonymisation) ---
FROM rust:1-slim AS rust
WORKDIR /src
COPY rust/datakit ./
RUN cargo build --release

# --- 2. L'application ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLEET_DB=/app/data/fleet.duckdb
WORKDIR /app
COPY requirements.txt .
# anthropic : la démo IA en ligne appelle le vrai modèle (clé dans le .env du serveur)
RUN pip install --no-cache-dir -r requirements.txt "anthropic>=0.40"
COPY app ./app
COPY --from=rust /src/target/release/datakit ./rust/datakit/target/release/datakit
# Utilisateur sans droits : une faille dans l'application ne donne pas la main sur le conteneur
RUN useradd --uid 10001 --no-create-home portfolio && mkdir -p /app/data && chown portfolio /app/data
USER portfolio
EXPOSE 8000
# --proxy-headers : derrière le Caddy de LTE, l'adresse du visiteur arrive dans X-Forwarded-For,
# et c'est elle que le quota de la démo IA doit compter, pas celle de Caddy.
CMD ["uvicorn", "app.presentation.web.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
