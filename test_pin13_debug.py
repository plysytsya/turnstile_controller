#!/usr/bin/env python3
# Debug script to test Pin 13 GPIO configuration

import gpiod
import time

# GPIO configuration
CHIP = "gpiochip0"
PIN13_OFFSET = 69  # Pin 13

def test_pin13():
    print("=== Pin 13 Debug Test ===")
    print(f"Testing Pin 13 (gpiochip0 line {PIN13_OFFSET})")
    
    try:
        # Get the chip
        chip = gpiod.Chip(CHIP)
        print(f"Successfully opened {CHIP}")
        
        # Get the line
        line = chip.get_line(PIN13_OFFSET)
        print(f"Successfully got line {PIN13_OFFSET}")
        
        # Check if line is available
        print(f"Line consumer: {line.consumer()}")
        print(f"Line direction: {line.direction()}")
        print(f"Line is_used: {line.is_used()}")
        
        # Try to request the line for output
        print("Attempting to request line for output...")
        line.request(consumer="debug_test", type=gpiod.LINE_REQ_DIR_OUT)
        print("Successfully requested line for output!")
        
        # Test toggling
        print("Testing GPIO toggle...")
        for i in range(5):
            value = 1 if i % 2 == 0 else 0
            line.set_value(value)
            print(f"Set line to {value}")
            time.sleep(0.5)
        
        # Clean up
        line.release()
        print("Line released successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Possible issues:")
        print("1. GPIO line might be in use by another process")
        print("2. GPIO line might need different permissions")
        print("3. GPIO line might not support output mode")
        
        # Try to get more info
        try:
            chip = gpiod.Chip(CHIP)
            line = chip.get_line(PIN13_OFFSET)
            print(f"\nLine info:")
            print(f"  Consumer: {line.consumer()}")
            print(f"  Direction: {line.direction()}")
            print(f"  Is used: {line.is_used()}")
        except:
            print("Could not get line info")

if __name__ == "__main__":
    test_pin13()