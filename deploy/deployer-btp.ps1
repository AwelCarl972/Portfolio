# Mise en ligne de la page BTP : image, données DECP + SIRENE, redémarrage. Lancé depuis la racine du dépôt.
# L'adresse du serveur n'est pas versionnée : elle se lit dans la variable d'environnement PORTFOLIO_HOTE
# (ex. utilisateur@adresse), à définir une fois sur le poste de déploiement.
$ErrorActionPreference = "Stop"
$hote = $env:PORTFOLIO_HOTE
if (-not $hote) { throw "Définissez PORTFOLIO_HOTE (utilisateur@adresse du serveur) avant de lancer le déploiement." }
$tag = git rev-parse --short HEAD
$tmp = Join-Path $env:TEMP "portfolio-deploy"
New-Item -ItemType Directory -Force $tmp | Out-Null

Write-Host "1/4 Image $tag -> archive (docker save)"
docker save -o "$tmp\image.tar" "portfolio/web:$tag" portfolio/web:latest
if ($LASTEXITCODE) { throw "docker save a échoué" }

Write-Host "2/4 Envoi de l'image et des données"
tar czf "$tmp\btp-data.tgz" -C data/raw decp_arrete2019.csv decp_arrete2022.csv sirene_decp.csv
scp "$tmp\image.tar" "$tmp\btp-data.tgz" "${hote}:/tmp/"
if ($LASTEXITCODE) { throw "scp a échoué" }

Write-Host "3/4 Chargement de l'image et des données sur le serveur"
ssh -t $hote "sudo docker load -i /tmp/image.tar && cd /srv/portfolio && sudo docker compose up -d && sudo docker compose cp /tmp/btp-data.tgz portfolio-web:/app/data/ && sudo docker compose exec -T portfolio-web sh -c 'mkdir -p data/raw && tar xzf data/btp-data.tgz -C data/raw && rm data/btp-data.tgz' && sudo docker compose restart portfolio-web && rm /tmp/image.tar /tmp/btp-data.tgz"
if ($LASTEXITCODE) { throw "le déploiement sur le serveur a échoué" }

Write-Host "4/4 Vérification"
# Le serveur calcule ses pages avant d'accepter des visiteurs : on attend qu'il réponde (2 min au plus)
$pret = $false
for ($i = 0; $i -lt 40 -and -not $pret; $i++) {
  Start-Sleep -Seconds 3
  try { $pret = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 https://axelclaude.fr/sante).StatusCode -eq 200 } catch { }
}
if (-not $pret) { throw "le site ne répond pas après 2 minutes" }
(Invoke-WebRequest -UseBasicParsing https://axelclaude.fr/btp).StatusCode
Remove-Item -Recurse -Force $tmp
