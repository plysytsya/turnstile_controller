#!/bin/bash

# Find and terminate all processes related to videocamera and videouploader
echo "Terminating videocamera and videouploader processes..."

# Get PIDs of processes named 'videocamera' or 'videouploader'
pids=$(ps aux | grep -E '[v]ideocamera|[v]ideouploader' | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "No videocamera or videouploader processes found."
else
    # Iterate through PIDs and terminate each one
    for pid in $pids; do
        echo "Killing process with PID: $pid"
        kill -9 $pid
    done
    echo "All videocamera and videouploader processes have been terminated."
fi
