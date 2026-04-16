#!/usr/bin/env python3
"""
Duales Studium München – täglicher Job-Scraper + Gemini-Analyse → Telegram

Quellen:
  - Bundesagentur für Arbeit (offizielle API, kein Auth nötig)
  - LinkedIn (öffentliche Job-Suche)
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime, date
from bs4 import BeautifulSoup

# ── Konfiguration ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SEEN_IDS_FILE = "seen_jobs.json"


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
def load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            data = json.load(f)
            cutoff = str(date.today())[:7]
            return set(
                jid for jid, seen_date in data.items()
                if seen_date[:7] >= cutoff
            )
    return set()


def save_seen_ids(seen: set, new_ids: list):
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


# ── Scraper: Bundesagentur für Arbeit ────────────────────────────────────────
def scrape_bundesagentur() -> list[dict]:
    """
    Öffentliche BA-API – kein OAuth, kein API-Key nötig.
    Einfach X-API-Key: jobboerse-jobsuche als Header.
    """
    jobs = []
    try:
        r = requests.get(
            "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs",
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "X-API-Key": "jobboerse-jobsuche",
            },
            params={
                "was": "duales Studium",
                "wo": "München",
                "umkreis": 25,
                "veroeffentlichtseit": 7,
                "size": 25,
                "page": 1,
            },
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        for item in data.get("stellenangebote") or []:
            title = item.get("titel", "–")
            company = item.get("arbeitgeber", "–")
            location = item.get("arbeitsort", {}).get("ort", "München")
            ref_nr = item.get("refnr", "")
            link = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref_nr}" if ref_nr else ""

            jobs.append({
                "id": make_id(title, company),
                "title": title,
                "company": company,
                "location": location,
                "snippet": item.get("kurzbeschreibung", "")[:300],
                "link": link,
                "source": "Bundesagentur für Arbeit",
            })

    except Exception as e:
        print(f"[Bundesagentur] Fehler: {e}")
    return jobs


# ── Scraper: LinkedIn ────────────────────────────────────────────────────────
def scrape_linkedin() -> list[dict]:
    jobs = []
    url = (
        "https://www.linkedin.com/jobs/search/"
        "?keywords=duales+Studium&location=M%C3%BCnchen&f_TPR=r604800&sortBy=DD"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.base-card")[:20]
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


# ── Gemini-Analyse ───────────────────────────────────────────────────────────
def analyze_with_gemini(jobs: list[dict]) -> str:
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

    prompt = f"""Du bist ein Karriere-Assistent. Analysiere die folgenden neuen dualen Studiengang-Stellen in München.

STELLEN:
{jobs_text}

Erstelle eine strukturierte Zusammenfassung auf Deutsch mit:
1. Überblick – Wie viele Stellen aus welchen Branchen?
2. Top-Empfehlungen – Die 3 interessantesten Stellen mit kurzer Begründung und direktem Link
3. Trends – Welche Unternehmen/Branchen suchen besonders aktiv?
4. Hinweise – Besonderheiten oder Auffälligkeiten

Halte es kompakt und lesbar für Telegram (kein Markdown, nur plain text mit Emojis)."""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 1500},
    }

    # Retry bei 429 mit exponentiellem Backoff
    for attempt in range(4):
        try:
            r = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if r.status_code == 429:
                wait = 20 * (2 ** attempt)  # 20s, 40s, 80s, 160s
                print(f"[Gemini] Rate limit – warte {wait}s (Versuch {attempt+1}/4)...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if attempt == 3:
                raise
            print(f"[Gemini] HTTP-Fehler: {e} – Versuch {attempt+1}/4")
            time.sleep(20)

    return "Fehler bei der Gemini-Analyse nach 4 Versuchen."


# ── Telegram-Versand ─────────────────────────────────────────────────────────
def send_telegram(message: str):
    today = datetime.now().strftime("%d.%m.%Y")
    full_message = f"🎓 Duales Studium München – {today}\n\n{message}"

    chunks = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
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

    all_jobs = []
    for scraper_fn in [scrape_bundesagentur, scrape_linkedin]:
        jobs = scraper_fn()
        print(f"  {scraper_fn.__name__}: {len(jobs)} Stellen gefunden")
        all_jobs.extend(jobs)
        time.sleep(3)

    # Deduplizieren
    seen_today = set()
    new_jobs = []
    for job in all_jobs:
        if job["id"] not in seen and job["id"] not in seen_today:
            new_jobs.append(job)
            seen_today.add(job["id"])

    print(f"📋 {len(new_jobs)} neue Stellen (nach Deduplizierung)")
    save_seen_ids(seen, list(seen_today))

    print("🤖 Gemini analysiert...")
    analysis = analyze_with_gemini(new_jobs)

    send_telegram(analysis)


if __name__ == "__main__":
    main()
