# PumpFun Livestream Chat Logger

Dieses Repository enthält ein kleines Hilfsskript, mit dem sich der Chat des
PumpFun-Livestreams als Textdatei (NDJSON) sichern lässt. Die einzelnen
Chat-Nachrichten werden inklusive Zeitstempel abgespeichert und können im
Anschluss weiter verarbeitet werden – zum Beispiel mit Python, Pandas oder
anderen Tools, die JSON verarbeiten.

## Installation

1. Optional: Erstelle und aktiviere ein virtuelles Python-Umfeld (z. B. mit
   `python -m venv .venv && source .venv/bin/activate`).
2. Installiere die Abhängigkeiten:

   ```bash
   pip install -r requirements.txt
   ```

## Verwendung

Das Skript `pumpfun_chat_logger.py` verbindet sich mit dem PumpFun-Socket.IO
Server und schreibt jede empfangene Chat-Nachricht als JSON-Zeile in die Datei
`pumpfun_chat.ndjson`. Die wichtigsten Parameter lassen sich über die
Kommandozeile anpassen, sodass Änderungen am PumpFun-Protokoll schnell
übernommen werden können.

```bash
python pumpfun_chat_logger.py \
  --socket-url https://pumpportal.fun \
  --subscribe-event subscribe \
  --subscribe-payload '{"room": "livestream", "channel": "chat"}' \
  --listen-event chat_message \
  --output pf_chat.ndjson \
  --header 'Cookie: cf_clearance=DEIN_WERT; another_cookie=...' \
  --header 'User-Agent: Mozilla/5.0 ...'
```

### Nützliche Optionen

- `--append`: hängt neue Nachrichten an eine bestehende Datei an.
- `--duration 600`: beendet das Skript nach 600 Sekunden automatisch.
- `--quiet`: unterdrückt die Ausgabe im Terminal (nur Datei wird geschrieben).
- Mehrfaches `--listen-event`: falls PumpFun mehrere Event-Namen für Chats
  verwendet, kann dieser Schalter mehrfach angegeben werden.
- `--header 'Key: Wert'`: ergänzt eigene HTTP-Header für den Socket.IO-Handshake.
- `--no-default-headers`: deaktiviert die automatisch gesetzten Browser-Header,
  falls du alle Felder selbst angeben möchtest.

## Authentifizierung & Header

Der Socket.IO-Endpunkt `pumpportal.fun` befindet sich hinter einer Web-
Application-Firewall. Damit die Verbindung akzeptiert wird, muss der Client
Browser-Header mitsenden (insbesondere `User-Agent`, `Origin`, `Referer`) und
ggf. gültige Cookies wie `cf_clearance` oder Sitzungs-Token. Standardmäßig
verschickt das Skript einen typischen Chrome-Header. Zusätzliche Felder kannst
du mit `--header KEY:VALUE` ergänzen.

Am einfachsten ist es, die Netzwerk-Tools des Browsers zu öffnen und nach dem
`socket.io`-Handshake der PumpFun-Webseite zu suchen. Kopiere dort sämtliche
Request-Header oder Cookies und füge sie dem Skript über wiederholte
`--header`-Argumente hinzu. Falls du deine eigenen Header vollständig angeben
möchtest, kannst du die Standardeinträge mit `--no-default-headers` deaktivieren.

## Ermittlung der richtigen Events

Die genauen Event-Namen und Payload-Strukturen können sich ändern. Mit den
Entwickler-Tools des Browsers (Tab „Netzwerk“) lässt sich beobachten, welche
Nachrichten die PumpFun-Webseite beim Beitritt zum Livestream verschickt. Diese
Informationen kannst du direkt an das Skript weiterreichen, ohne den Code
ändern zu müssen.

## Ausgabeformat

Jede Zeile der Ausgabedatei enthält einen JSON-Datensatz mit:

- `timestamp`: Zeitpunkt des Empfangs im ISO-8601-Format (UTC).
- `event`: Name des Socket.IO-Events.
- `data`: Unveränderte Nutzlast, die PumpFun gesendet hat.

Die NDJSON-Datei lässt sich beispielsweise mit `jq`, Python oder Datenbank-Tools
weiter analysieren.
