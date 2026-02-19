"""
Envoi du digest email quotidien des meilleures annonces.
Compatible SMTP standard (Gmail, OVH, etc.)
"""

import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from villa_search.models import Listing

logger = logging.getLogger(__name__)

# Couleurs du scoring
SCORE_COLORS = {
    "Excellent deal": "#1a7f37",
    "Bon rapport qualite/prix": "#0969da",
    "Prix marche": "#bf8700",
    "Surevalue": "#d1242f",
}

SCORE_EMOJI = {
    "Excellent deal": "🟢",
    "Bon rapport qualite/prix": "🔵",
    "Prix marche": "🟡",
    "Surevalue": "🔴",
}


def send_daily_digest(listings: list[Listing], config: dict) -> bool:
    """
    Envoie un email HTML récapitulatif des annonces du jour.
    Retourne True si l'envoi a réussi.
    """
    email_cfg = config.get("email", {})
    smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(email_cfg.get("smtp_port", 587))
    sender = email_cfg.get("sender", "")
    recipients = email_cfg.get("recipients", [])
    subject_prefix = email_cfg.get("subject_prefix", "[Villa Marrakech]")

    # Mot de passe via variable d'environnement (ne jamais mettre en dur)
    password = os.environ.get("VILLA_SMTP_PASSWORD", "")

    if not sender or not recipients:
        logger.error("Email non configuré (sender / recipients manquants).")
        return False

    if not password:
        logger.error("Variable d'environnement VILLA_SMTP_PASSWORD non définie.")
        return False

    today = date.today().strftime("%d/%m/%Y")
    subject = f"{subject_prefix} Récap du {today} — {len(listings)} annonce(s) sélectionnée(s)"

    html_body = _build_html(listings, today, config)
    text_body = _build_text(listings, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        logger.info(f"Email envoyé à {recipients} ({len(listings)} annonces).")
        return True
    except Exception as e:
        logger.error(f"Échec envoi email: {e}")
        return False


def _build_html(listings: list[Listing], today: str, config: dict) -> str:
    search_cfg = config.get("search", {})
    neighborhood = search_cfg.get("neighborhood", "Marrakech")

    cards_html = "".join(_listing_card_html(l) for l in listings)

    if not listings:
        cards_html = """
        <div style="text-align:center; padding:40px; color:#57606a;">
            <p style="font-size:18px;">Aucune nouvelle annonce aujourd'hui.</p>
            <p>Les critères de recherche sont peut-être trop restrictifs, ou le marché est calme.</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Villa Marrakech – Récap du {today}</title>
</head>
<body style="margin:0; padding:0; background:#f6f8fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;">

<div style="max-width:680px; margin:0 auto; padding:24px 16px;">

  <!-- Header -->
  <div style="background:#0d1117; border-radius:12px; padding:28px 32px; margin-bottom:24px; text-align:center;">
    <h1 style="color:#f0f6fc; margin:0 0 8px; font-size:22px;">
      Villa Marrakech – {neighborhood}
    </h1>
    <p style="color:#8b949e; margin:0; font-size:14px;">
      Récapitulatif du {today} · {len(listings)} annonce(s) sélectionnée(s)
    </p>
  </div>

  <!-- Légende scores -->
  <div style="background:#fff; border:1px solid #d0d7de; border-radius:8px; padding:16px 20px; margin-bottom:20px;">
    <p style="margin:0 0 10px; font-weight:600; color:#24292f; font-size:13px; text-transform:uppercase; letter-spacing:.5px;">
      Légende du scoring
    </p>
    <div style="display:flex; flex-wrap:wrap; gap:12px;">
      <span style="background:#dafbe1; color:#116329; padding:4px 10px; border-radius:20px; font-size:13px; font-weight:500;">🟢 Excellent deal ≥ 75/100</span>
      <span style="background:#ddf4ff; color:#0550ae; padding:4px 10px; border-radius:20px; font-size:13px; font-weight:500;">🔵 Bon rapport 55-74/100</span>
      <span style="background:#fff8c5; color:#7d4e00; padding:4px 10px; border-radius:20px; font-size:13px; font-weight:500;">🟡 Prix marché 35-54/100</span>
      <span style="background:#ffebe9; color:#b91c1c; padding:4px 10px; border-radius:20px; font-size:13px; font-weight:500;">🔴 Surévalué &lt; 35/100</span>
    </div>
  </div>

  <!-- Annonces -->
  {cards_html}

  <!-- Footer -->
  <div style="text-align:center; padding:20px 0; color:#57606a; font-size:12px; border-top:1px solid #d0d7de; margin-top:24px;">
    <p style="margin:0;">Généré automatiquement · Sources: Avito · Mubawab · Yakeey</p>
    <p style="margin:4px 0 0;">Pour modifier les critères, éditez <code>villa_search/config.yaml</code></p>
  </div>

</div>
</body>
</html>"""


def _listing_card_html(l: Listing) -> str:
    label = l.score_label or "N/A"
    color = SCORE_COLORS.get(label, "#57606a")
    emoji = SCORE_EMOJI.get(label, "⚪")
    score = f"{l.total_score:.0f}/100" if l.total_score is not None else "N/A"

    price_str = f"{l.price_mad:,} MAD".replace(",", " ") if l.price_mad else "Prix non communiqué"
    surface_str = f"{l.surface_m2} m²" if l.surface_m2 else "N/A"
    rooms_str = f"{l.bedrooms} ch." if l.bedrooms else "N/A"
    bath_str = f"{l.bathrooms} sdb" if l.bathrooms else ""

    vs_market = ""
    if l.price_vs_market is not None:
        sign = "+" if l.price_vs_market > 0 else ""
        # price_vs_market positif = moins cher que le marché
        direction = "sous le marché" if l.price_vs_market > 0 else "au-dessus du marché"
        vs_market = f"<span style='font-size:12px; color:{color};'>({sign}{l.price_vs_market:.1f}% {direction})</span>"

    image_html = ""
    if l.images:
        image_html = f"""<img src="{l.images[0]}" alt="photo" style="width:100%; height:200px; object-fit:cover; border-radius:6px 6px 0 0; display:block;">"""

    badge_new = """<span style="background:#0969da; color:#fff; font-size:11px; font-weight:600; padding:2px 8px; border-radius:20px; margin-left:8px;">NOUVEAU</span>""" if l.is_new else ""

    desc_short = (l.description or "")[:280] + ("..." if len(l.description or "") > 280 else "")

    return f"""
<div style="background:#fff; border:1px solid #d0d7de; border-radius:8px; margin-bottom:16px; overflow:hidden;">
  {image_html}
  <div style="padding:16px 20px;">

    <!-- Titre + badge -->
    <div style="margin-bottom:10px;">
      <span style="background:{color}20; color:{color}; font-size:12px; font-weight:600; padding:2px 10px; border-radius:20px;">{emoji} {label} · {score}</span>
      {badge_new}
    </div>

    <h2 style="margin:0 0 6px; font-size:16px; color:#24292f; line-height:1.4;">
      <a href="{l.url}" style="color:#0969da; text-decoration:none;">{l.title}</a>
    </h2>

    <!-- Prix -->
    <p style="margin:0 0 10px; font-size:20px; font-weight:700; color:#24292f;">
      {price_str} {vs_market}
    </p>

    <!-- Caractéristiques -->
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
      <span style="background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:4px 10px; font-size:13px; color:#57606a;">🛏 {rooms_str}</span>
      <span style="background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:4px 10px; font-size:13px; color:#57606a;">📐 {surface_str}</span>
      {"<span style='background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:4px 10px; font-size:13px; color:#57606a;'>🚿 " + bath_str + "</span>" if bath_str else ""}
      <span style="background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:4px 10px; font-size:13px; color:#57606a;">📍 {l.neighborhood or "Marrakech"}</span>
      <span style="background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:4px 10px; font-size:13px; color:#57606a;">🏠 {l.source.capitalize()}</span>
    </div>

    <!-- Description courte -->
    <p style="margin:0 0 14px; font-size:13px; color:#57606a; line-height:1.6;">
      {desc_short}
    </p>

    <!-- CTA -->
    <a href="{l.url}" style="display:inline-block; background:#0d1117; color:#f0f6fc; text-decoration:none; padding:8px 18px; border-radius:6px; font-size:13px; font-weight:600;">
      Voir l'annonce →
    </a>
  </div>
</div>"""


def _build_text(listings: list[Listing], today: str) -> str:
    lines = [
        f"VILLA MARRAKECH – RÉCAP DU {today}",
        f"{len(listings)} annonce(s) sélectionnée(s)",
        "=" * 60,
        "",
    ]
    for i, l in enumerate(listings, 1):
        score = f"{l.total_score:.0f}/100" if l.total_score else "N/A"
        price = f"{l.price_mad:,} MAD".replace(",", " ") if l.price_mad else "N/A"
        lines += [
            f"{i}. [{l.score_label or 'N/A'} – {score}] {l.title}",
            f"   Prix    : {price}",
            f"   Surface : {l.surface_m2 or 'N/A'} m²",
            f"   Chambres: {l.bedrooms or 'N/A'}",
            f"   Quartier: {l.neighborhood or 'N/A'}",
            f"   Source  : {l.source}",
            f"   Lien    : {l.url}",
            "",
        ]
    lines.append("Généré automatiquement par villa_search.")
    return "\n".join(lines)
