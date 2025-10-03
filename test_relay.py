# dual_relay_test.py
# This script controls two relays connected to ODROID pins.
# Relay 1: Pin 7 - gpiochip0 line 62
# Relay 2: Pin 13 - gpiochip0 line 69
# Press '1' + Enter to toggle relay 1, '2' + Enter to toggle relay 2, 'q' + Enter to quit

import gpiod

# GPIO configuration
CHIP = "gpiochip0"
RELAY1_OFFSET = 62  # Pin 7 (existing relay)
RELAY2_OFFSET = 69  # Pin 13 (new relay) - corrected!

# Many 3-pin relay boards are active-low:
ACTIVE_LOW = True
OFF = 1 if ACTIVE_LOW else 0
ON  = 0 if ACTIVE_LOW else 1

def setup_gpio():
    """Initialize GPIO lines for both relays"""
    chip = gpiod.Chip(CHIP)
    
    relay1_line = chip.get_line(RELAY1_OFFSET)
    relay2_line = chip.get_line(RELAY2_OFFSET)
    
    # Request lines for output
    relay1_line.request(consumer="relay1", type=gpiod.LINE_REQ_DIR_OUT)
    relay2_line.request(consumer="relay2", type=gpiod.LINE_REQ_DIR_OUT)
    
    # Start with both relays OFF
    relay1_line.set_value(OFF)
    relay2_line.set_value(OFF)
    
    return relay1_line, relay2_line

def main():
    print("=== Dual Relay Test ===")
    print("Relay 1: Pin 7 (gpiochip0 line 62)")
    print("Relay 2: Pin 13 (gpiochip0 line 69)")
    print("\nControls:")
    print("  Type '1' + Enter to toggle Relay 1")
    print("  Type '2' + Enter to toggle Relay 2")
    print("  Type 'q' + Enter to quit")
    print("\nBoth relays starting in OFF state...")
    
    # Initialize GPIO
    try:
        relay1_line, relay2_line = setup_gpio()
        print("GPIO initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize GPIO: {e}")
        return
    
    # Track relay states
    relay1_state = OFF
    relay2_state = OFF
    
    print("Ready! Type commands now...")
    
    try:
        while True:
            command = input("> ").strip().lower()
            
            if command == '1':
                # Toggle relay 1
                relay1_state = ON if relay1_state == OFF else OFF
                relay1_line.set_value(relay1_state)
                status = "ON" if relay1_state == ON else "OFF"
                print(f"Relay 1: {status}")
                
            elif command == '2':
                # Toggle relay 2
                relay2_state = ON if relay2_state == OFF else OFF
                relay2_line.set_value(relay2_state)
                status = "ON" if relay2_state == ON else "OFF"
                print(f"Relay 2: {status}")
                
            elif command == 'q' or command == 'quit':
                print("Exiting...")
                break
                
            elif command == '':
                continue  # Empty input, just continue
                
            else:
                print("Invalid command. Type '1', '2', or 'q'")
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Always turn off both relays and release GPIO
        print("Turning off both relays...")
        relay1_line.set_value(OFF)
        relay2_line.set_value(OFF)
        relay1_line.release()
        relay2_line.release()
        print("GPIO released. Script terminated.")

if __name__ == "__main__":
    main()