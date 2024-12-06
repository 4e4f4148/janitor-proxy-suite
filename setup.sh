#!/bin/bash

# Exit on error
set -e

# Check if Python is installed
if ! command -v python3 &>/dev/null; then
    echo "Python3 is not installed or not in PATH."
    echo "Please install Python3 and add it to PATH."
    exit 1
fi

# Create a virtual environment named .venv
echo "Creating virtual environment .venv..."
python3 -m venv .venv

# Activate the virtual environment
echo "Activating the virtual environment..."
source .venv/bin/activate

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "requirements.txt not found. Skipping installation of dependencies."
    deactivate
    exit 0
fi

# Install dependencies from requirements.txt
echo "Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "All dependencies installed successfully!"