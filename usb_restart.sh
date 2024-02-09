#!/bin/bash

# Define the path to uhubctl
UHUBCTL_PATH="/home/pi/uhubctl"

# Turn off all specified USB ports on hub 1-1
sudo $UHUBCTL_PATH/uhubctl -a off -p 1,2,3,4 -l 1-1

# Print a message and wait for 3 seconds
echo "Specified USB devices powered off. Waiting for 3 seconds..."
sleep 3

# Turn on all specified USB ports on hub 1-1
sudo $UHUBCTL_PATH/uhubctl -a on -p 1,2,3,4 -l 1-1

# Print a message indicating completion
echo "Specified USB devices powered back on."

# Wait for an additional 3 seconds before the script ends
echo "Waiting for 3 more seconds before the script ends..."
sleep 3

# Print a message indicating the end of the script
echo "Script execution complete."
