#!/usr/bin/env node
 

/**
 * Script to generate logo variants from robot-logo.png
 * Generates:
 * - mark-16.png: 16x16 logo
 * - mark-32.png: 32x32 logo
 * - mark-48.png: 48x48 logo
 * - mark-64.png: 64x64 logo
 * - mark-96.png: 96x96 logo
 * - mark-128.png: 128x128 logo
 * - mark-128-padded.png: 128x128 logo with 96x96 content + 16px padding
 * - mark-256.png: 256x256 logo
 */

const fs = require('fs');
const path = require('path');

// Check if Sharp is installed (optional dependency)
/* eslint-disable import/no-unresolved */
let sharp;
try {
  sharp = require('sharp');
} catch (error) {
  console.error('Error: Sharp package is not installed.');
  console.error('Please install it first with: npm install sharp');
  process.exit(1);
}
/* eslint-enable import/no-unresolved */

const assetsDir = path.join(__dirname, '..', 'robotframework-recorder-assets');
const outputDir = path.join(__dirname, '..', 'assets');
const sourceFile = path.join(assetsDir, 'robot-logo.png');

// Check if source file exists
if (!fs.existsSync(sourceFile)) {
  console.error(`Error: Source file not found: ${sourceFile}`);
  process.exit(1);
}

console.log('🤖 Generating logo variants...\n');

const sizes = [16, 32, 48, 64, 96, 128, 256];
const promises = [];

// Generate each size
sizes.forEach((size) => {
  console.log(`📐 Generating mark-${size}.png (${size}x${size})...`);

  const promise = sharp(sourceFile)
    .resize(size, size, {
      fit: 'contain',
      background: {
        r: 255, g: 255, b: 255, alpha: 0
      }
    })
    .png()
    .toFile(path.join(outputDir, `mark-${size}.png`))
    .then(() => {
      console.log(`✅ mark-${size}.png created successfully`);
    })
    .catch((err) => {
      console.error(`❌ Error creating mark-${size}.png:`, err.message);
      process.exit(1);
    });

  promises.push(promise);
});

// Generate mark-128-padded.png after all sizes are done
Promise.all(promises)
  .then(() => {
    console.log('\n📐 Generating mark-128-padded.png (128x128 with padding)...');
    return sharp(sourceFile)
      .resize(96, 96, {
        fit: 'contain',
        background: {
          r: 255, g: 255, b: 255, alpha: 0
        }
      })
      .extend({
        top: 16,
        bottom: 16,
        left: 16,
        right: 16,
        background: {
          r: 255, g: 255, b: 255, alpha: 0
        }
      })
      .png()
      .toFile(path.join(outputDir, 'mark-128-padded.png'));
  })
  .then(() => {
    console.log('✅ mark-128-padded.png created successfully');
    console.log('\n🎉 All logos generated successfully!');
    console.log(`📁 Output location: ${outputDir}`);
  })
  .catch((err) => {
    console.error('❌ Error creating mark-128-padded.png:', err.message);
    process.exit(1);
  });
