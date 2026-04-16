#!/usr/bin/env python3
"""
Duales Studium München – täglicher Job-Scraper + Claude-Analyse → Telegram
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime, date
from bs4 import BeautifulSoup

# ── Konfiguration ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SEEN_IDS_FILE = "seen_jobs.json"  # wird im GitHub Actions Workspace gespeichert


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
def load_seen_ids() -> set:
    """Lädt bereits bekannte Job-IDs (Deduplizierung über Tage)."""
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            data = json.load(f)
            # Nur die letzten 7 Tage behalten
            cutoff = str(date.today())
            return set(
                jid for jid, seen_date in data.items()
                if seen_date >= cutoff[:8]  # YYYY-MM
            )
    return set()


def save_seen_ids(seen: set, new_ids: list):
    """Speichert Job-IDs mit heutigem Datum."""
    existing = {}
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            existing = json.load(f)
    today = str(date.today())
    for jid in new_ids:
        existing[jid] = today
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


def make_id(title: str, company: str) -> str:
    return hashlib.md5(f"{title}|{company}".lower().encode()).hexdigest()[:12]


# ── Scraper: Indeed ──────────────────────────────────────────────────────────
def scrape_indeed() -> list[dict]:
    jobs = []
    url = (
        "https://de.indeed.com/jobs"
        "?q=duales+Studium&l=M%C3%BCnchen&sort=date&fromage=1"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.job_seen_beacon")[:15]
        for card in cards:
            title_el = card.select_one("h2.jobTitle span[title]")
            company_el = card.select_one("span.companyName")
            location_el = card.select_one("div.companyLocation")
            snippet_el = card.select_one("div.job-snippet")
            link_el = card.select_one("a[href]")

            title = title_el["title"] if title_el else "–"
            company = company_el.get_text(strip=True) if company_el else "–"
            location = location_el.get_text(strip=True) if location_el else "München"
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            link = "https://de.indeed.com" + link_el["href"] if link_el else ""

            jobs.append({
                "id": make_id(title, company),
                "title": title,
                "company": company,
                "location": location,
                "snippet": snippet[:300],
                "link": link,
                "source": "Indeed",
            })
    except Exception as e:
        print(f"[Indeed] Fehler: {e}")
    return jobs


# ── Scraper: Stepstone ───────────────────────────────────────────────────────
def scrape_stepstone() -> list[dict]:
    jobs = []
    url = (
        "https://www.stepstone.de/jobs/duales-studium/in-muenchen"
        "?ag=age_1&sort=2"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("article[data-at='job-item']")[:15]
        for card in cards:
            title_el = card.select_one("h2[data-at='job-item-title']")
            company_el = card.select_one("span[data-at='job-item-company-name']")
            location_el = card.select_one("span[data-at='job-item-location']")
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else "–"
            company = company_el.get_text(strip=True) if company_el else "–"
            location = location_el.get_text(strip=True) if location_el else "München"
            link = link_el["href"] if link_el else ""
            if link and not link.startswith("http"):
                link = "https://www.stepstone.de" + link

            jobs.append({
                "id": make_id(title, company),
                "title": title,
                "company": company,
                "location": location,
                "snippet": "",
                "link": link,
                "source": "Stepstone",
            })
    except Exception as e:
        print(f"[Stepstone] Fehler: {e}")
    return jobs


# ── Scraper: Ausbildung.de ───────────────────────────────────────────────────
def scrape_ausbildung_de() -> list[dict]:
    jobs = []
    url = (
        "https://www.ausbildung.de/duales-studium/stellen/"
        "?location=M%C3%BCnchen&radius=20"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.ResultItem")[:15]
        for card in cards:
            title_el = card.select_one("h3") or card.select_one("h2")
            company_el = card.select_one("span.company") or card.select_one("p.company")
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else "–"
            company = company_el.get_text(strip=True) if company_el else "–"
            link = link_el["href"] if link_el else ""
            if link and not link.startswith("http"):
                link = "https://www.ausbildung.de" + link

            jobs.append({
                "id": make_id(title, company),
                "title": title,
                "company": company,
                "location": "München",
                "snippet": "",
                "link": link,
                "source": "Ausbildung.de",
            })
    except Exception as e:
        print(f"[Ausbildung.de] Fehler: {e}")
    return jobs


# ── Scraper: LinkedIn ────────────────────────────────────────────────────────
def scrape_linkedin() -> list[dict]:
    jobs = []
    url = (
        "https://www.linkedin.com/jobs/search/"
        "?keywords=duales+Studium&location=M%C3%BCnchen&f_TPR=r86400&sortBy=DD"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.base-card")[:15]
        for card in cards:
            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else "–"
            company = company_el.get_text(strip=True) if company_el else "–"
            location = location_el.get_text(strip=True) if location_el else "München"
            link = link_el["href"].split("?")[0] if link_el else ""

            jobs.append({
                "id": make_id(title, company),
                "title": title,
                "company": company,
                "location": location,
                "snippet": "",
                "link": link,
                "source": "LinkedIn",
            })
    except Exception as e:
        print(f"[LinkedIn] Fehler: {e}")
    return jobs


# ── Claude-Analyse ───────────────────────────────────────────────────────────
def analyze_with_claude(jobs: list[dict]) -> str:
    if not jobs:
        return "Heute wurden keine neuen Stellen gefunden."

    jobs_text = "\n\n".join(
        f"#{i+1} [{j['source']}] {j['title']}\n"
        f"  Unternehmen: {j['company']}\n"
        f"  Ort: {j['location']}\n"
        f"  Beschreibung: {j['snippet'] or '(keine)'}\n"
        f"  Link: {j['link']}"
        for i, j in enumerate(jobs)
    )

    prompt = f"""Du bist ein Karriere-Assistent. Analysiere die folgenden neuen dualen Studiengang-Stellen in München vom heutigen Tag.

STELLEN:
{jobs_text}

Erstelle eine strukturierte Zusammenfassung auf Deutsch mit:
1. **Überblick** – Wie viele Stellen aus welchen Branchen?
2. **Top-Empfehlungen** – Die 3 interessantesten Stellen mit kurzer Begründung und direktem Link
3. **Trends** – Welche Unternehmen/Branchen suchen besonders aktiv?
4. **Hinweise** – Besonderheiten oder Auffälligkeiten

Halte es kompakt und lesbar für Telegram (kein HTML, nur plain text mit Emojis)."""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


# ── Telegram-Versand ─────────────────────────────────────────────────────────
def send_telegram(message: str):
    today = datetime.now().strftime("%d.%m.%Y")
    full_message = f"🎓 Duales Studium München – {today}\n\n{message}"

    # Telegram hat ein 4096-Zeichen-Limit
    chunks = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        r.raise_for_status()
        time.sleep(0.5)
    print(f"✅ Telegram-Nachricht gesendet ({len(chunks)} Teil(e))")


# ── Hauptprogramm ────────────────────────────────────────────────────────────
def main():
    print(f"🔍 Starte Job-Scraping – {datetime.now().isoformat()}")

    seen = load_seen_ids()

    # Alle Portale scrapen
    all_jobs = []
    for scraper_fn in [scrape_indeed, scrape_stepstone, scrape_ausbildung_de, scrape_linkedin]:
        jobs = scraper_fn()
        print(f"  {scraper_fn.__name__}: {len(jobs)} Stellen gefunden")
        all_jobs.extend(jobs)
        time.sleep(2)  # höfliche Pause zwischen Requests

    # Duplikate entfernen (global + tagesübergreifend)
    seen_today = set()
    new_jobs = []
    for job in all_jobs:
        if job["id"] not in seen and job["id"] not in seen_today:
            new_jobs.append(job)
            seen_today.add(job["id"])

    print(f"📋 {len(new_jobs)} neue Stellen (nach Deduplizierung)")

    # IDs speichern
    save_seen_ids(seen, list(seen_today))

    # Claude-Analyse
    print("🤖 Claude analysiert...")
    analysis = analyze_with_claude(new_jobs)

    # Telegram senden
    send_telegram(analysis)


if __name__ == "__main__":
    main()
