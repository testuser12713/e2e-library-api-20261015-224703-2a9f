# Stadtbibliothek API

Eine REST-API für die Ausleihe einer kleinen Stadtbibliothek. Die API verwaltet
Bücher, Mitglieder und Ausleihen, erzwingt die drei Leihregeln (höchstens drei
offene Ausleihen je Mitglied, Ausleihe nur bei freiem Exemplar, Rückgabe
schließt die Ausleihe), schützt alle schreibenden Endpunkte per `X-API-Key` und
antwortet auf jeden Fehler in einem einheitlichen Format. Dieser Stand ist das
lauffähige Gerüst: Routen, Datenmodelle, Schemas und Fehlerformat sind
vollständig verdrahtet, die Fachlogik der einzelnen Router folgt in
nachgelagerten Tickets.

## Tech-Stack

- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2 und pydantic-settings
- SQLAlchemy 2.0 (typisiert, deklarativ)
- SQLite (Datei, über SQLAlchemy)
- pytest mit dem FastAPI-TestClient
- ruff

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Konfiguration

Die Konfiguration wird aus Umgebungsvariablen gelesen (optional auch aus einer
`.env`-Datei):

| Variable          | Pflicht | Default                  | Bedeutung                                   |
| ----------------- | ------- | ------------------------ | ------------------------------------------- |
| `LIBRARY_API_KEY` | ja      | –                        | API-Key für alle schreibenden Endpunkte     |
| `DATABASE_URL`    | nein    | `sqlite:///./library.db` | Verbindung zur Datenbank                    |

`LIBRARY_API_KEY` hat bewusst keinen Default — der Server startet nur, wenn die
Variable gesetzt ist. Ein Beispiel für eine lokale Entwicklungsumgebung:

```bash
export LIBRARY_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DATABASE_URL="sqlite:///./library.db"
```

## Start (Entwicklung)

```bash
uvicorn app.main:app --reload
```

Der Server läuft dann unter <http://127.0.0.1:8000>. Beim Start wird die
SQLite-Datei angelegt und das Schema (`books`, `members`, `loans`) erzeugt —
eine manuelle Migration ist nicht nötig.

## Build (Produktion)

Es gibt keinen separaten Build-Schritt; das Produkt läuft direkt aus dem
Quellcode. Für einen Produktivstart ohne Auto-Reload:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Verwendung

Interaktive Dokumentation: <http://127.0.0.1:8000/docs> (OpenAPI-Schema unter
`/openapi.json`).

Lesende Endpunkte (kein API-Key nötig):

| Methode | Pfad             | Beschreibung                                            |
| ------- | ---------------- | ------------------------------------------------------- |
| GET     | `/health`        | Health-Check, antwortet `{"status": "ok"}`              |
| GET     | `/books`         | Bücher auflisten (`q`, `limit`, `offset`)               |
| GET     | `/books/{id}`    | Ein Buch lesen                                          |
| GET     | `/members`       | Mitglieder auflisten (`limit`, `offset`)                |
| GET     | `/members/{id}`  | Ein Mitglied lesen                                      |
| GET     | `/loans`         | Ausleihen auflisten (`member_id`, `book_id`, `active`)  |
| GET     | `/loans/overdue` | Überfällige Ausleihen                                   |
| GET     | `/loans/{id}`    | Eine Ausleihe lesen                                     |

Schreibende Endpunkte (Header `X-API-Key` mit dem konfigurierten Wert nötig):

| Methode | Pfad                 | Beschreibung                       |
| ------- | -------------------- | ---------------------------------- |
| POST    | `/books`             | Buch anlegen (201)                 |
| PUT     | `/books/{id}`        | Buch vollständig ersetzen (200)    |
| PATCH   | `/books/{id}`        | Buch teilweise ändern (200)        |
| DELETE  | `/books/{id}`        | Buch löschen (204)                 |
| POST    | `/members`           | Mitglied anlegen (201)             |
| PUT     | `/members/{id}`      | Mitglied vollständig ersetzen (200) |
| PATCH   | `/members/{id}`      | Mitglied teilweise ändern (200)    |
| DELETE  | `/members/{id}`      | Mitglied löschen (204)             |
| POST    | `/loans`             | Ausleihe anlegen (201)             |
| POST    | `/loans/{id}/return` | Ausleihe zurückgeben (200)         |

Beispiel mit API-Key:

```bash
curl -X POST http://127.0.0.1:8000/books \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $LIBRARY_API_KEY" \
  -d '{"title":"Der Prozess","author":"Franz Kafka","isbn":"9783150091901","publication_year":1925,"total_copies":3}'
```

Jede Fehlerantwort hat die einheitliche Form:

```json
{"error": {"code": "NOT_FOUND", "message": "...", "details": null}}
```

Die Codes sind `UNAUTHORIZED` (401), `NOT_FOUND` (404), `CONFLICT` (409) und
`VALIDATION_ERROR` (422).

## Tests

```bash
PYTHONPATH=. python -m pytest
```

Die Tests laufen mit dem FastAPI-TestClient gegen eine eigene temporäre
Testdatenbank — ohne laufenden Server und ohne den `LIBRARY_API_KEY` manuell zu
setzen (der Test-Key wird zur Laufzeit erzeugt).

## Funktionen

- Lauffähiges API-Gerüst mit FastAPI, Pydantic v2 und SQLAlchemy 2.0 auf SQLite
- Vollständige Datenmodelle `Book`, `Member`, `Loan` samt `utcnow()`-Helfer
- Alle Endpunkte des Vertrags deklariert (Pfad, Methode, Status, Modell, Key-Pflicht)
- Einheitliches Fehlerformat über zentrale Exception-Handler
- Konfiguration ausschließlich aus der Umgebung (kein Schlüssel im Quellcode)
- Schema-Erzeugung beim Start, damit ein frisch geklonter Stand sofort läuft
