# 🎓 Duales Studium München – Täglicher Job-Agent

Scrapet täglich neue duale Studiengang-Stellen in München von **Indeed, Stepstone, Ausbildung.de und LinkedIn**, analysiert sie mit Claude und sendet eine Zusammenfassung per Telegram.

---

## 🚀 Setup (einmalig, ~10 Minuten)

### 1. Repository erstellen

```bash
# Neues GitHub-Repo anlegen (z.B. "duales-studium-agent")
# Dann diese Dateien hochladen:
# - scraper.py
# - .github/workflows/daily_jobs.yml
# - seen_jobs.json  (leer: {})
```

### 2. GitHub Secrets hinterlegen

Gehe zu: **Repository → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Wert | Wo bekommst du ihn? |
|---|---|---|
| `GEMINI_API_KEY` | `AIza...` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (kostenlos) |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | Bereits in deinem maxi-bot vorhanden |
| `TELEGRAM_CHAT_ID` | `-100123456` oder `123456` | Siehe unten |

### 3. Telegram Chat-ID herausfinden

Schreib deinem Bot eine Nachricht, dann ruf auf:
```
https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates
```
→ Suche nach `"chat": {"id": ...}` – das ist deine Chat-ID.

### 4. Ersten Lauf testen

GitHub → Actions → **"Duales Studium München"** → **"Run workflow"**

---

## ⏰ Zeitplan

| Tag | Uhrzeit |
|---|---|
| Mo–Fr | 08:00 Uhr MESZ (Sommer) |
| Sa–So | 08:00 Uhr MEZ (Winter) |

> **Hinweis:** GitHub Actions Cron läuft in UTC. Der Workflow hat zwei Cron-Einträge um Sommer-/Winterzeit abzudecken. An Übergangswochenenden kann die Nachricht ±1h versetzt kommen.

---

## 📁 Dateistruktur

```
duales-studium-agent/
├── scraper.py                        # Haupt-Skript
├── seen_jobs.json                    # Cache (wird auto-committed)
└── .github/
    └── workflows/
        └── daily_jobs.yml            # GitHub Actions Workflow
```

---

## 🔧 Anpassungen

**Andere Suchbegriffe** – in `scraper.py` die URL-Parameter ändern:
```python
# Indeed
"?q=duales+Studium+Informatik&l=München"
# Stepstone  
"/jobs/duales-studium-informatik/in-muenchen"
```

**Mehr/weniger Stellen** – `[:15]` in den Scrapern anpassen.

**Nur werktags** – Cron auf `0 6 * * 1-5` beschränken (bereits so konfiguriert).

---

## ⚠️ Hinweise

- Die Scraper basieren auf dem aktuellen HTML-Aufbau der Portale. Wenn ein Portal sein Layout ändert, muss der Selektor angepasst werden.
- LinkedIn blockiert gelegentlich Bots. Falls LinkedIn-Ergebnisse fehlen, ist das normal.
- `seen_jobs.json` wird täglich ins Repo committed – so werden keine Stellen doppelt gemeldet.
