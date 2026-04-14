#!/bin/sh
mogrify -resize 1280x800 -background '#F0F0F0' -gravity center -extent 1280x800 -quality 100 main-view.png
mogrify -resize 1280x800 -background '#F0F0F0' -gravity center -extent 1280x800 -quality 100 scan-output.png
mogrify -resize 1280x800 -background '#F0F0F0' -gravity center -extent 1280x800 -quality 100 settings-view.png
