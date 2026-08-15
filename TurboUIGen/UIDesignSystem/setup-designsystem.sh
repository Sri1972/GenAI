#!/bin/bash
echo "=== Installing Mobility Global Design System dependencies ==="
cd "$(dirname "$0")"
npm install
echo ""
echo "Done! Run 'npm run storybook' to start Storybook."
