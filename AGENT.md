# AGENT.md – rekordbox PDB Patcher

## Was das Tool macht

Konvertiert Audiodateien auf einem Rekordbox-USB-Stick in CDJ-kompatible Formate (FLAC/ALAC → AIFF, M4A/OGG/WMA → MP3) und patcht **alle** Metadaten-Datenbanken so, dass Cues, Beatgrids und Hot Cues erhalten bleiben.

## Wichtige Architektur-Entscheidungen

### Dateinamenlänge bleibt gleich
`.flac` (5 Zeichen) → `.aiff` (5 Zeichen)
`.m4a` (4 Zeichen) → `.mp3` (4 Zeichen)
Pflicht: Binäre Offsets in der PDB dürfen sich nicht verschieben.

### Was gepatcht wird

| Datei | Was |
|---|---|
| `PIONEER/rekordbox/export.pdb` | Dateipfade + **Format-Type-Codes** |
| `PIONEER/rekordbox/exportExt.pdb` | Dateipfade |
| `PIONEER/USBANLZ/**/*.DAT/.EXT/.2EX` | Dateipfade in ASCII + UTF-16BE |
| `exportLibrary.db` (Library Plus) | **Wird nicht angefasst** (proprietär/verschlüsselt) |

## PDB Format-Type-Codes (kritisch!)

In jedem Track-Record der `export.pdb` steckt ein Tagged-Field-Sequenz:

```
\x03 \x05 [CODE1] \x05 [CODE2] \x03
```

Diese beiden Bytes sagen dem CDJ, welches Audioformat die Datei hat.
Ohne diesen Patch wird die Datei als FLAC erkannt, obwohl sie schon AIFF ist.

**Bekannte Werte (durch Binärvergleich ermittelt):**

| Format | CODE1 | CODE2 | Hex-Pattern |
|--------|-------|-------|-------------|
| FLAC   | `0x33` ('3') | `0x32` ('2') | `03 05 33 05 32 03` |
| WAV    | `0x34` ('4') | `0x32` ('2') | `03 05 34 05 32 03` |
| AIFF   | `0x34` ('4') | `0x34` ('4') | `03 05 34 05 34 03` |
| MP3    | (anderes Schema, kein Patch nötig) | | `03 07 32 37 05 32 05 35 03` |

**Noch unbekannt:** ALAC-Codes (kein Sample-PDB vorhanden).

Das Mapping steht in `PDB_FORMAT_CODE_PATCHES` in `patcher.py` (Zeile ~18).

## Konvertierungs-Modi

- **Standard (SSD-Cache):** 8 parallele Worker → Temp-Ordner → auf USB kopieren
- `--on-device`: 2 Worker, direkt auf USB (langsamer, weniger RAM)
- `--patch-only`: Nur PDB/ANLZ patchen, nicht konvertieren
- `--convert-only`: Nur konvertieren, nicht patchen
- `--keep-originals`: Originaldateien nicht löschen

## Bekannte Grenzen / TODOs

- `exportLibrary.db` (Library Plus, verschlüsselt/proprietär) wird **nicht** gepatcht.
  Tracks sind auf älteren CDJ-Geräten problemlos nutzbar, aber die Cloud-Sync-Library erkennt das konvertierte Format möglicherweise falsch.
- ALAC → AIFF: Format-Type-Code noch unbekannt. Sobald ein ALAC-PDB-Sample vorliegt, `PDB_FORMAT_CODE_PATCHES` ergänzen.
- Nur für USB-Exporte gedacht, nicht für die interne rekordbox-Library auf dem Mac/PC.

## Entwicklungs-Referenz

```
example_new/
  unmodified/   ← Original-USB-Export (4 Tracks: FLAC, WAV, MP3, AIFF)
  modified/     ← Manuell gepatchtes Referenzergebnis zum Vergleichen
```

Zum Prüfen ob ein Patch korrekt ist:
```bash
cmp -l example_new/modified/PIONEER/rekordbox/export.pdb /tmp/test_patched.pdb
```
Die einzigen harmlosen Abweichungen sind Bytes 17 + 21 (Header-Counter, werden von rekordbox selbst gesetzt).
