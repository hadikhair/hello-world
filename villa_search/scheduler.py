"""
Scheduler quotidien.

Usage:
    python -m villa_search.scheduler              # tourne en continu, exécute à l'heure config.yaml
    python -m villa_search.scheduler --now        # exécute immédiatement (utile pour tester)
    python -m villa_search.scheduler --dry-run    # exécute sans envoyer d'email
"""

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import yaml

from villa_search.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def next_run_seconds(target_time: str, tz_name: str = "Africa/Casablanca") -> float:
    """
    Calcule le nombre de secondes avant la prochaine exécution à l'heure cible.
    On utilise l'heure locale du système ; pour une précision TZ, installe pytz.
    """
    now = datetime.now()
    hour, minute = map(int, target_time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        # L'heure est passée aujourd'hui → on vise demain
        from datetime import timedelta
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main():
    parser = argparse.ArgumentParser(description="Villa search scheduler")
    parser.add_argument("--now", action="store_true", help="Exécuter immédiatement")
    parser.add_argument("--dry-run", action="store_true", help="Sans envoi d'email")
    args = parser.parse_args()

    config = load_config()
    scheduler_cfg = config.get("scheduler", {})
    run_at = scheduler_cfg.get("run_at", "08:00")
    tz = scheduler_cfg.get("timezone", "Africa/Casablanca")

    if args.now or args.dry_run:
        logger.info("Exécution immédiate du pipeline...")
        results = run_pipeline(config, dry_run=args.dry_run)
        logger.info(f"Pipeline terminé: {len(results)} annonces retenues.")
        return

    logger.info(f"Scheduler démarré. Prochaine exécution quotidienne à {run_at} ({tz}).")

    while True:
        wait = next_run_seconds(run_at, tz)
        h, m = divmod(int(wait), 3600)
        m, s = divmod(m, 60)
        logger.info(f"Prochain run dans {h}h {m}min {s}s (à {run_at}).")
        time.sleep(wait)

        logger.info("=== Démarrage du pipeline villa search ===")
        try:
            config = load_config()  # rechargement à chaque run (config peut changer)
            results = run_pipeline(config)
            logger.info(f"Pipeline terminé: {len(results)} annonces envoyées.")
        except Exception as e:
            logger.exception(f"Erreur pipeline: {e}")

        # Petite pause pour ne pas re-déclencher immédiatement
        time.sleep(60)


if __name__ == "__main__":
    main()
