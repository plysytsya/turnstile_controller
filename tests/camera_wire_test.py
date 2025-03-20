import time

import spidev
import RPi.GPIO as GPIO


# Define CE and CSN pins
CE_PIN = 25  # Change this if using a different CE pin
CSN_PIN = 8  # CE0 (Physical pin 24)

# Initialize SPII conne
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI bus 0, device 0 (CS0)
spi.max_speed_hz = 4000000  # Set SPI speed (4 MHz)

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(CE_PIN, GPIO.OUT)
GPIO.output(CE_PIN, GPIO.LOW)  # Set CE low to start


def read_register(reg):
    """Read a register from the nRF24L01 module."""
    response = spi.xfer2([reg, 0xFF])  # Send register address, read response
    return response[1]


def check_nrf24():
    """Check if the nRF24L01 is wired correctly."""
    try:
        # Activate the module by setting CE HIGH (temporary)
        GPIO.output(CE_PIN, GPIO.HIGH)
        time.sleep(0.01)  # Give the module time to power up

        # Read the STATUS register (0x07)
        status = read_register(0x07)

        # Deactivate CE after reading
        GPIO.output(CE_PIN, GPIO.LOW)

        if status != 0xFF:  # If response is not 0xFF, the module is detected
            print(f"✅ nRF24L01 detected! STATUS register: 0x{status:02X}")
        else:
            print("❌ No response from nRF24L01. Check your wiring!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        spi.close()  # Close SPI
        GPIO.cleanup()  # Clean up GPIO



# Run the test
if __name__ == "__main__":
    check_nrf24()
