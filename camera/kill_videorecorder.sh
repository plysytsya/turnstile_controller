#!/bin/bash

# Find and terminate all processes related to videocamera
echo "Terminating videocamera processes..."

# Get PIDs of processes named 'videocamera'
pids=$(ps aux | grep -E '[v]ideocamera' | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "No videocamera processes found."
else
    # Iterate through PIDs and terminate each one
    for pid in $pids; do
        echo "Killing process with PID: $pid"
        kill -9 $pid
    done
    echo "All videocamera processes have been terminated."
fi
