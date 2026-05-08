# Logo Generator Scripts

Diese Scripts generieren Logo-Varianten aus der `robot-logo.png` Datei.

## Generierte Dateien

- **mark-16.png**: 16x16 Pixel großes Logo
- **mark-32.png**: 32x32 Pixel großes Logo
- **mark-48.png**: 48x48 Pixel großes Logo
- **mark-64.png**: 64x64 Pixel großes Logo
- **mark-96.png**: 96x96 Pixel großes Logo
- **mark-128.png**: 128x128 Pixel großes Logo
- **mark-128-padded.png**: 128x128 Pixel großes Logo mit 96x96 Inhalt + 16px Padding
- **mark-256.png**: 256x256 Pixel großes Logo

## Optionen

Es gibt drei Möglichkeiten, die Scripts auszuführen:

### Option 1: Bash Script (empfohlen für macOS)

```bash
./script/generate-logos.sh
```

Dieses Script versucht automatisch, entweder Sharp (Node.js) oder ImageMagick zu verwenden.

### Option 2: Python Script

Voraussetzungen:
```bash
pip install Pillow
```

Ausführung:
```bash
python script/generate-logos.py
```

### Option 3: Node.js Script

Voraussetzungen:
```bash
npm install sharp
```

Ausführung:
```bash
node script/generate-logos.js
```

## Erforderliche Tools

Wählen Sie eine der folgenden Optionen:

### A) Mit Sharp (Node.js)
```bash
npm install sharp
# oder global
npm install -g sharp
```

### B) Mit ImageMagick
```bash
# macOS (Homebrew)
brew install imagemagick

# Linux (Ubuntu/Debian)
sudo apt-get install imagemagick

# Linux (Fedora)
sudo dnf install ImageMagick
```

### C) Mit Python/Pillow
```bash
pip install Pillow
```

## Troubleshooting

**Fehler: "sharp is not installed"**
- Führen Sie `npm install sharp` aus

**Fehler: "convert command not found"**
- Installieren Sie ImageMagick mit `brew install imagemagick`

**Fehler: "Pillow is not installed"**
- Führen Sie `pip install Pillow` aus

## Tipps

- Die Bash-Version ist am benutzerfreundlichsten und versucht, die beste verfügbare Option zu finden
- Das Python-Script ist plattformübergreifend kompatibel
- Das Node.js-Script hat die beste Bildqualität mit Sharp
