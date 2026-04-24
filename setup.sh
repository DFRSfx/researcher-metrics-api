#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt
pip install selenium webdriver-manager
echo ""
echo "Setup complete. Run ./start.sh to launch the API."
