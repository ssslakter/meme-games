#!/bin/bash

# Define the project path (this will be set via an environment variable in GitHub)
PROJECT_PATH="$1"  # Passed as a command-line argument

# Define the path to the virtual environment inside the project directory
VENV_PATH="$PROJECT_PATH/.env"

# Check if the virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found, creating a new one..."
    python3 -m venv "$VENV_PATH"
else
    echo "Virtual environment already exists, activating it..."
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Navigate to the project directory
cd "$PROJECT_PATH" || exit

# Pull the latest changes from the main branch
git pull origin main || exit

# Install/update dependencies
pip install -e . || exit

# Kill the existing Python app
pkill -f "python run.py" || echo "No existing instance to kill"

# Define the log file location
LOG_FILE="$PROJECT_PATH/deployment.log"

# Clear the log file before starting the application (optional)
> "$LOG_FILE"

# Run the Python application (main.py) and log both stdout and stderr to the log file
echo "Starting the application and logging output to $LOG_FILE"

python run.py >> "$LOG_FILE" 2>&1 &

# Capture the PID of the background process (Python app)
APP_PID=$!

# Optionally, you can monitor the process and write to the log
# Wait for the app to run (this is just an example, modify based on your needs)
wait $APP_PID

echo "Deployment and application startup successful!"
