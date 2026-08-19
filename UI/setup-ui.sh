#!/bin/bash
echo "=== Installing TurboUI Dashboard dependencies ==="
cd "$(dirname "$0")"
npm install
echo ""
echo "Done! Run 'npm run dev' to start the dashboard."
