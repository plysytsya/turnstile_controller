# conftest.py
import sys
import os

# Calculate the directory that is one level up
one_level_up = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Print the directory name
print(f"Directory one level up: {one_level_up}")

# Add the directory that is one level up to the Python path
sys.path.insert(0, one_level_up)
