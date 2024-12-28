#!/bin/bash

# Find and terminate all processes related to videocamera
echo "Terminating pyvideorecorder processes..."

# Get PIDs of processes named 'pyvideorecorder'
pids=$(ps aux | grep -E 'pyvideorecorder' | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "No pyvideorecorder processes found."
else
    # Iterate through PIDs and terminate each one
    for pid in $pids; do
        echo "Killing process with PID: $pid"
        kill -9 $pid
    done
    echo "All pyvideorecorder processes have been terminated."
fi
