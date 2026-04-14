# Logo Converter

Konvertiert die `robot-logo.png` mit folgenden Änderungen:
- **Farbe**: Ändert zu `#00c0b5` (Türkis)
- **Padding**: Reduziert durch Trimmen und neues Padding (8x8px)
- **Strokes**: Verdickt durch Morphologie-Filter

## Ausführung

### Option 1: Bash (ImageMagick)
```bash
./convert-logo.sh
```

Benötigt ImageMagick:
```bash
brew install imagemagick
```

### Option 2: Python (Pillow)
```bash
python convert-logo.py
```

Benötigt Pillow:
```bash
pip install Pillow
```

## Ergebnis

Das Logo wird umgewandelt und direkt in `robotframework-recorder-assets/robot-logo.png` gespeichert.

Nach der Konvertierung können Sie das generiert-Logo-Script ausführen:
```bash
./generate-logos
```

Dies erzeugt alle Logo-Varianten (16, 32, 48, 64, 96, 128, 128-padded, 256) mit der neuen Farbe.
