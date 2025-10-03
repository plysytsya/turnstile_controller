# Debug version of dual relay test
import gpiod

# GPIO configuration
CHIP = "gpiochip0"
RELAY1_OFFSET = 62  # Pin 7
RELAY2_OFFSET = 69  # Pin 13

ACTIVE_LOW = True
OFF = 1 if ACTIVE_LOW else 0
ON  = 0 if ACTIVE_LOW else 1

def main():
    print("=== Dual Relay Debug ===")
    print(f"Relay 1: Pin 7 (gpiochip0 line {RELAY1_OFFSET})")
    print(f"Relay 2: Pin 13 (gpiochip0 line {RELAY2_OFFSET})")
    
    try:
        chip = gpiod.Chip(CHIP)
        
        # Get both lines
        relay1_line = chip.get_line(RELAY1_OFFSET)
        relay2_line = chip.get_line(RELAY2_OFFSET)
        
        print(f"\nBefore requesting:")
        print(f"Relay1 line {RELAY1_OFFSET} - used: {relay1_line.is_used()}, consumer: {relay1_line.consumer()}")
        print(f"Relay2 line {RELAY2_OFFSET} - used: {relay2_line.is_used()}, consumer: {relay2_line.consumer()}")
        
        # Request lines
        relay1_line.request(consumer="relay1", type=gpiod.LINE_REQ_DIR_OUT)
        relay2_line.request(consumer="relay2", type=gpiod.LINE_REQ_DIR_OUT)
        
        print(f"\nAfter requesting:")
        print(f"Relay1 line {RELAY1_OFFSET} - used: {relay1_line.is_used()}, consumer: {relay1_line.consumer()}")
        print(f"Relay2 line {RELAY2_OFFSET} - used: {relay2_line.is_used()}, consumer: {relay2_line.consumer()}")
        
        # Set both OFF initially
        relay1_line.set_value(OFF)
        relay2_line.set_value(OFF)
        print("\nBoth relays set to OFF")
        
        # Track states
        relay1_state = OFF
        relay2_state = OFF
        
        print("\nTest commands:")
        print("1 = toggle relay 1 only")
        print("2 = toggle relay 2 only")
        print("q = quit")
        
        while True:
            command = input("> ").strip().lower()
            
            if command == '1':
                relay1_state = ON if relay1_state == OFF else OFF
                print(f"Setting relay1 line {RELAY1_OFFSET} to {relay1_state}")
                relay1_line.set_value(relay1_state)
                status = "ON" if relay1_state == ON else "OFF"
                print(f"Relay 1: {status}")
                
            elif command == '2':
                relay2_state = ON if relay2_state == OFF else OFF
                print(f"Setting relay2 line {RELAY2_OFFSET} to {relay2_state}")
                relay2_line.set_value(relay2_state)
                status = "ON" if relay2_state == ON else "OFF"
                print(f"Relay 2: {status}")
                
            elif command == 'q':
                break
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            relay1_line.set_value(OFF)
            relay2_line.set_value(OFF)
            relay1_line.release()
            relay2_line.release()
        except:
            pass
        print("Cleanup done")

if __name__ == "__main__":
    main()