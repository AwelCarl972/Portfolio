# Mise en ligne du portfolio (axelclaude.fr)

Le portfolio tourne sur le serveur de LoueTonEngin et MonGrosEngin, dans sa propre pile
(`/srv/portfolio`). Le Caddy de LTE sert le domaine et lui passe les visiteurs par le réseau
Docker `frontal` (fichier `deploy/caddy/sites/axelclaude.caddy` du dépôt LTE).

Ce qui le sépare des deux autres sites :

- **sa pile** : ni la base ni l'API de LTE ou de MGE ne sont sur le réseau `frontal` ;
- **ses plafonds** : 384 Mo de mémoire et un demi-cœur. S'il dépasse, c'est lui que Docker
  redémarre ;
- **son image construite sur le poste** : le serveur ne compile rien.

## 1. Le domaine

Chez le registraire, faire pointer `axelclaude.fr` et `www.axelclaude.fr` (enregistrements `A`,
et `AAAA` si le serveur a une IPv6) vers l'adresse du serveur, **avant** de recharger Caddy :
il demande son certificat dès qu'il lit le bloc du domaine.

## 2. L'image (sur le poste)

```bash
T=$(git rev-parse --short HEAD)
docker build -t portfolio/web:$T -t portfolio/web:latest .
docker save portfolio/web:$T portfolio/web:latest | gzip -1 | ssh <admin>@<hôte> 'gunzip | sudo docker load'
```

## 3. La pile (sur le serveur, la première fois)

```bash
scp deploy/compose.yaml deploy/.env.example <admin>@<hôte>:/tmp/
# puis, sur le serveur :
sudo mkdir -p /srv/portfolio && sudo cp /tmp/compose.yaml /srv/portfolio/
sudo cp /tmp/.env.example /srv/portfolio/.env && sudo nano /srv/portfolio/.env   # ANTHROPIC_API_KEY
cd /srv/portfolio && sudo docker compose up -d
```

La pile LTE doit tourner avant : elle crée le réseau `frontal`.

## 4. Les données (une fois, puis à chaque mise à jour des sources)

L'open data se télécharge depuis le serveur, dans le volume :

```bash
cd /srv/portfolio
sudo docker compose exec portfolio-web python -m app.infrastructure.opendata.fetch
```

Les projets (carte des bornes, rapports MetaTrader) partent du poste, déjà aplatis :

```bash
# sur le poste
tar czf projets.tgz -C data/raw projets && scp projets.tgz <admin>@<hôte>:/tmp/
# sur le serveur
cd /srv/portfolio
sudo docker compose cp /tmp/projets.tgz portfolio-web:/app/data/
sudo docker compose exec portfolio-web sh -c 'mkdir -p data/raw && tar xzf data/projets.tgz -C data/raw && rm data/projets.tgz'
sudo docker compose restart portfolio-web
```

Les tables sont reconstruites à chaque démarrage depuis ces fichiers : un redémarrage suffit.

## 5. Le domaine dans Caddy (pile LTE)

Une fois la PR du dépôt LTE fusionnée, copier `deploy/caddy/sites/axelclaude.caddy` dans
`/srv/lte/caddy/sites/`, puis :

```bash
cd /srv/lte && sudo docker compose exec caddy caddy reload -c /etc/caddy/Caddyfile
```

## 6. Vérifier

```bash
curl -I https://axelclaude.fr/sante          # 200
sudo docker stats --no-stream                 # la part de chacun des trois sites
```

Puis ouvrir `/observatoire`, `/projets`, et lancer une analyse sur la page d'accueil : la réponse
ne doit plus porter la mention « Réponse simulée ».

## La démo IA et son coût

Chaque analyse est payée par la clé du `.env`. Deux plafonds la protègent (`LLM_QUOTA_VISITEUR`
par heure, `LLM_QUOTA_JOUR` pour tous) ; les compteurs vivent en mémoire et repartent à zéro au
redémarrage. Fixer aussi une **limite de dépense mensuelle** dans la console Anthropic : c'est le
seul plafond qui tient même si l'application a un défaut.
