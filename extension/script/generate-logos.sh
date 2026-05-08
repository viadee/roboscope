#!/bin/bash

# Script to generate logo variants from robot-logo.png
# Uses ImageMagick (convert) or Sharp (Node.js)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ASSETS_DIR="$PROJECT_ROOT/robotframework-recorder-assets"
OUTPUT_DIR="$PROJECT_ROOT/assets"
SOURCE_FILE="$ASSETS_DIR/robot-logo.png"

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🤖 Logo Generator${NC}\n"

# Check if source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo -e "${RED}❌ Error: Source file not found: $SOURCE_FILE${NC}"
    exit 1
fi

# Try to use Sharp (Node.js) first
if command -v node &> /dev/null; then
    echo -e "${BLUE}📦 Using Node.js with Sharp...${NC}\n"
    node "$SCRIPT_DIR/generate-logos.js"
    exit $?
fi

# Fallback to ImageMagick if available
if command -v convert &> /dev/null; then
    echo -e "${BLUE}📦 Using ImageMagick...${NC}\n"
    
    # Generate all standard sizes
    for size in 16 32 48 64 96 128 256; do
        echo -e "${BLUE}📐 Generating mark-${size}.png (${size}x${size})...${NC}"
        convert "$SOURCE_FILE" \
            -background none \
            -gravity center \
            -resize ${size}x${size} \
            -extent ${size}x${size} \
            "$OUTPUT_DIR/mark-${size}.png"
        echo -e "${GREEN}✅ mark-${size}.png created successfully${NC}\n"
    done
    
    # Generate 128x128 with padding (96x96 content + 16px padding)
    echo -e "${BLUE}📐 Generating mark-128-padded.png (128x128 with padding)...${NC}"
    convert "$SOURCE_FILE" \
        -background none \
        -gravity center \
        -resize 96x96 \
        -extent 128x128 \
        "$OUTPUT_DIR/mark-128-padded.png"
    echo -e "${GREEN}✅ mark-128-padded.png created successfully${NC}\n"
    
    echo -e "${GREEN}🎉 All logos generated successfully!${NC}"
    echo -e "${BLUE}📁 Output location: $OUTPUT_DIR${NC}"
    exit 0
fi

# If neither is available, print instructions
echo -e "${RED}❌ Error: Neither Node.js with Sharp nor ImageMagick found.${NC}\n"
echo -e "${BLUE}Installation options:${NC}\n"
echo "1. Install Node.js and Sharp:"
echo "   npm install sharp"
echo ""
echo "2. Or install ImageMagick:"
echo "   brew install imagemagick"
exit 1
