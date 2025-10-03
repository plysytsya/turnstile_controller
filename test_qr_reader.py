#!/usr/bin/env python3

import serial
import serial.tools.list_ports
import time
import sys

def test_qr_reader():
    """Test QR reader connected via serial USB"""
    
    # Try common serial device paths
    possible_devices = ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/ttyUSB1']
    
    ser = None
    device_path = None
    
    # Find the QR reader device
    for device in possible_devices:
        try:
            print(f"Trying to connect to {device}...")
            ser = serial.Serial(
                port=device,
                baudrate=9600,  # Common baudrate for QR readers
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            device_path = device
            print(f"Successfully connected to QR reader at {device}")
            break
        except Exception as e:
            print(f"Failed to connect to {device}: {e}")
            continue
    
    if not ser:
        print("Could not find QR reader on any serial port!")
        print("Available devices:")
        for port in serial.tools.list_ports.comports():
            print(f"  {port.device} - {port.description}")
        return
    
    print(f"\n=== QR Reader Test Started ===")
    print(f"Connected to: {device_path}")
    print("Please scan a QR code. Press Ctrl+C to exit.\n")
    
    try:
        buffer = ""
        while True:
            if ser.in_waiting > 0:
                # Read data from serial port
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                buffer += data
                
                # Process complete lines (QR codes usually end with newline)
                while '\n' in buffer or '\r' in buffer:
                    if '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                    else:
                        line, buffer = buffer.split('\r', 1)
                    
                    line = line.strip()
                    if line:  # Only print non-empty lines
                        print(f"QR Code scanned: {line}")
                        print(f"Length: {len(line)} characters")
                        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print("-" * 50)
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error reading from serial port: {e}")
    finally:
        if ser:
            ser.close()
            print(f"Disconnected from {device_path}")

if __name__ == "__main__":
    test_qr_reader()