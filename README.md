# hello-world
My first repository

Hello !

This my first trial on github. I hope I'll give it enough time and energy to be something else than just another failed project.

---

# Villa Search – Marrakech

Outil d'automatisation de recherche de villa à Marrakech.
Scrape Avito, Mubawab et Yakeey, filtre, dédoublonne, score les prix et envoie un récap email quotidien.

## Fonctionnalités

- **Scraping multi-sources** : Avito.ma, Mubawab.ma, Yakeey.com
- **Filtrage intelligent** : chambres, surface, budget, mots-clés modernes/exclus
- **Déduplication** : hash exact + similarité titre (~85%) pour éviter les doublons cross-sources
- **Scoring prix /100** basé sur le prix au m² vs le marché Targa
- **Digest email HTML** quotidien avec classement, badges de score et liens directs
- **Scheduler** autonome (tourne en fond, pas besoin de cron système)

## Structure

```
villa_search/
├── config.yaml          ← Tous tes critères ici
├── models.py            ← Dataclass Listing
├── pipeline.py          ← Orchestrateur principal
├── scheduler.py         ← Runner quotidien autonome
├── scraper/
│   ├── avito.py
│   ├── mubawab.py
│   └── yakeey.py
├── filter/engine.py     ← Règles de filtrage
├── scorer/engine.py     ← Algorithme de scoring
├── dedup/store.py       ← Déduplication persistante
└── mailer/digest.py     ← Email HTML + texte
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Édite `villa_search/config.yaml` :

```yaml
search:
  neighborhood: Targa
  min_bedrooms: 4
  max_price_mad: 15000000
  style_keywords: [moderne, contemporain, neuf, standing]

email:
  sender: ton_email@gmail.com
  recipients: [ton_email@gmail.com]

scheduler:
  run_at: "08:00"
```

Pour Gmail, crée un **App Password** (pas ton mot de passe principal) :
→ Compte Google > Sécurité > Mots de passe des applications

## Utilisation

### Test immédiat (sans email)
```bash
export VILLA_SMTP_PASSWORD="ton_app_password"
python -m villa_search.scheduler --dry-run
```

### Lancement en mode démon
```bash
export VILLA_SMTP_PASSWORD="ton_app_password"
python -m villa_search.scheduler
```
L'outil tourne en continu et envoie un email chaque matin à l'heure configurée.

### Lancer maintenant (avec email)
```bash
python -m villa_search.scheduler --now
```

## Scoring des annonces

| Score | Label | Signification |
|-------|-------|---------------|
| >= 75 | Excellent deal | Prix significativement sous le marché |
| 55-74 | Bon rapport qualité/prix | Légèrement sous ou dans le marché |
| 35-54 | Prix marché | Prix conforme au marché |
| < 35  | Surévalué | Prix au-dessus du marché |

Le scoring combine (pondération configurable) :
- **Prix (40%)** : prix/m² vs médiane marché Targa
- **Surface (25%)** : surface brute
- **Localisation (20%)** : Targa > Amelkis > Agdal > Hivernage...
- **Style (15%)** : présence de mots-clés modernes dans l'annonce

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `VILLA_SMTP_PASSWORD` | Mot de passe SMTP (Gmail App Password) |

## Mise à jour du prix de référence marché

Modifie `market_price_per_m2` dans `config.yaml` selon l'évolution du marché :

```yaml
scoring:
  market_price_per_m2: 12000   # MAD/m² – prix médian Targa
```
