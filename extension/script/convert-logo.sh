#!/bin/bash
# Convert robot-logo.png: trim padding, apply color #00c0b5
convert /Users/rat/git/Robocorp-Recorder/robotframework-recorder-assets/robot-logo.png -trim -bordercolor none -border 8x8 -morphology Dilate Octagon:1.5 -fill '#00c0b5' -colorize 100 /Users/rat/git/Robocorp-Recorder/robotframework-recorder-assets/robot-logo.png && echo "✅ Logo converted: color changed to #00c0b5"
