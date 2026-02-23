#!/bin/bash
set -e

echo "Packaging LegalMind Agent for Antigravity..."

# 1. Build Tools
echo "Building legalmind-tools..."
cd legalmind-tools
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run build
cd ..

# 2. Create Zip
OUTPUT_FILE="legalmind_agent_package.zip"
rm -f "$OUTPUT_FILE"

echo "Creating zip package..."
zip -r "$OUTPUT_FILE" \
    openclaw-agent \
    legalmind-tools/package.json \
    legalmind-tools/dist \
    legalmind-tools/node_modules \
    -x "*.git*" -x "*__pycache__*" -x "*.DS_Store*"

echo "Done! Package created: $OUTPUT_FILE"
