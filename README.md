# OWM Vereinsportal

Das OWM Vereinsportal ist ein Django-Backend für vereinsrelevante Aufgaben der
[Offenen Werkstatt Mainz e.V.](https://offenewerkstattmainz.de).
Jede Aufgabe ist eine eigene Django-App:

| App      | Pfad            | Zweck                                                   |
|----------|-----------------|---------------------------------------------------------|
| `core`   | `/`             | Startseite, gemeinsames Layout, statische Dateien       |
| `voting` | `/bieterrunde/` | Interaktive Bieterrunde (siehe unten)                   |

Das Django-Projektpaket (Settings, URLs, WSGI) liegt in `owm_portal/`.

# Bieterrunde

## Was ist das?

Die App `voting` dient zum interaktiven Abhalten von [Bieterrunden](https://www.solidarische-landwirtschaft.org/fileadmin/media/solidarische-landwirtschaft.org/Solawis-aufbauen/Vorlagen-Dokumente/Netzwerk-Solawi-Bieterrunde.pdf).
Hier wurde die Variante "mit Richtwert" umgesetzt.


## Warum?

Die [Offenen Werkstatt Mainz e.V.](https://offenewerkstattmainz.de) verwendet Bieterrunden um auf solidarische weise Mitgliedsbeiträge festzulegen.
Auf vergangenen Mitgliederversammlungen wurde dies mit Zettel und Stift durchgeführt und anschließend manuell ausgewertet.

Da dieser Prozess sehr Zeitaufwendig ist, entstand die Idee ein Tool zu entwickeln, welches diesen Prozess vereinfacht und beschleunigt.

## Wie funktioniert es?

TBD

## Dev Setup

Das Projekt nutzt [mise](https://mise.jdx.dev) als dependency manager.
Ein development setup kann mit den folgenden Befehlen aufgesetzt werden:

```bash
mise install
uv sync
```

## Upgrade von der alten „bieterrunde“-Installation

Mit dem Umbau zum OWM Vereinsportal haben sich geändert:

- Docker-Image: `ghcr.io/offenewerkstattmainz/owm-portal` (Variable `OWM_PORTAL_IMAGE`
  statt `BIETERRUNDE_IMAGE`)
- Datenbankname: `owm_portal` statt `bieterrunde` (überschreibbar per `DB_NAME`)
- Die Bieterrunde liegt jetzt unter `/bieterrunde/`. Alte Links werden dauerhaft weitergeleitet.

Die bestehende Datenbank muss einmalig umbenannt werden, bevor das neue Image startet:

```bash
docker compose stop web worker
docker compose exec db psql -U postgres -c 'ALTER DATABASE bieterrunde RENAME TO owm_portal;'
docker compose up -d
```
