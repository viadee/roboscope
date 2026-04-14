#!/bin/bash
# zipping for chrome webstore

FILE="manifest.json"
while IFS= read -r line
do
  if [[ $line == *\"version\"* ]]; then
    VERSION=$(echo $line| cut -d':' -d'"' -f 4)
  fi
done < "$FILE"

echo $VERSION

mkdir -p archive
# zip -r archive/${VERSION}.zip . -x *.git* *.DS_Store *.idea* *.zip script/\* archive/\* test/\* node_modules/\* package* .eslint* docs/\* yarn.lock yarn-error.log .travis.yml .nyc_output/\* .husky/\*
zip -r archive/${VERSION}.zip . -i vendors/* assets/**/* assets/* src/**/* src/* LICENSE CHANGELOG.md README.md manifest.json

cp archive/${VERSION}.zip archive/latest.zip

exit;
