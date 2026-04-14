#!/usr/bin/env python

"""
Script to generate logo variants from robot-logo.png
Generates:
- mark-16.png: 16x16 logo
- mark-32.png: 32x32 logo
- mark-48.png: 48x48 logo
- mark-64.png: 64x64 logo
- mark-96.png: 96x96 logo
- mark-128.png: 128x128 logo
- mark-128-padded.png: 128x128 logo with 96x96 content + 16px padding
- mark-256.png: 256x256 logo
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow (PIL) is not installed.")
    print("Please install it with: pip install Pillow")
    sys.exit(1)


def generate_logos():
    """Generate logo variants from robot-logo.png"""
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    assets_dir = project_root / "robotframework-recorder-assets"
    output_dir = project_root / "assets"
    source_file = assets_dir / "robot-logo.png"
    
    # Check if source file exists
    if not source_file.exists():
        print(f"❌ Error: Source file not found: {source_file}")
        sys.exit(1)
    
    print("🤖 Generating logo variants...\n")
    
    # Open the source image
    try:
        img = Image.open(source_file)
    except Exception as e:
        print(f"❌ Error opening source file: {e}")
        sys.exit(1)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Define all sizes
    sizes = [16, 32, 48, 64, 96, 128, 256]
    
    # Generate each size
    for size in sizes:
        print(f"📐 Generating mark-{size}.png ({size}x{size})...")
        try:
            logo = Image.new('RGBA', (size, size), (255, 255, 255, 0))
            
            # Resize the source image to fit within the target size
            img_resized = img.copy()
            img_resized.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Paste the resized image in the center
            offset = ((size - img_resized.width) // 2, (size - img_resized.height) // 2)
            logo.paste(img_resized, offset, img_resized)
            
            # Save as PNG
            logo.save(output_dir / f"mark-{size}.png", 'PNG')
            print(f"✅ mark-{size}.png created successfully")
        except Exception as e:
            print(f"❌ Error creating mark-{size}.png: {e}")
            sys.exit(1)
    
    print()
    
    # Generate mark-128-padded.png
    print("📐 Generating mark-128-padded.png (128x128 with padding)...")
    try:
        # Create a new image with transparent background (128x128)
        logo_128 = Image.new('RGBA', (128, 128), (255, 255, 255, 0))
        
        # Resize the source image to 96x96
        img_resized = img.copy()
        img_resized.thumbnail((96, 96), Image.Resampling.LANCZOS)
        
        # Paste the 96x96 image in the center (leaving 16px padding on each side)
        offset = ((128 - img_resized.width) // 2, (128 - img_resized.height) // 2)
        logo_128.paste(img_resized, offset, img_resized)
        
        # Save as PNG
        logo_128.save(output_dir / "mark-128-padded.png", 'PNG')
        print("✅ mark-128-padded.png created successfully\n")
    except Exception as e:
        print(f"❌ Error creating mark-128-padded.png: {e}")
        sys.exit(1)
    
    print("🎉 All logos generated successfully!")
    print(f"📁 Output location: {output_dir}")


if __name__ == "__main__":
    generate_logos()
