#!/bin/bash

# ============================
# Setup script for gen_agg_auth_stat.py
# ============================

# Name of virtual environment
VENV_NAME="myenv"

echo "Setting up Python virtual environment..."

# Create virtual environment if not exists
if [ ! -d "$VENV_NAME" ]; then
    python3 -m venv $VENV_NAME
    echo "Virtual environment '$VENV_NAME' created."
else
    echo "Virtual environment '$VENV_NAME' already exists."
fi

# Activate virtual environment
source $VENV_NAME/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install required packages
echo "Installing required packages..."
pip install pandas requests tabulate

# Create necessary directories
mkdir -p temp log data

echo "Setup complete!"
echo "To activate the virtual environment, run:"
echo "    source $VENV_NAME/bin/activate"
echo "Then you can run the script:"
echo "    python3 script/gen_agg_auth_stat.py facultydb/<faculty_list.csv>"

