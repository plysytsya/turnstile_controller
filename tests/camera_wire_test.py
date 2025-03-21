import time

import spidev
import RPi.GPIO as GPIO


# Define CE and CSN pins
CE_PIN = 26  # Change this if using a different CE pin
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
    """Verifica si el módulo nRF24L01 está cableado correctamente."""
    try:
        # Activar el módulo configurando CE en ALTO (temporalmente)
        GPIO.output(CE_PIN, GPIO.HIGH)
        time.sleep(0.01)  # Dar tiempo al módulo para encenderse

        # Leer el registro STATUS (0x07)
        status = read_register(0x07)

        # Desactivar CE después de la lectura
        GPIO.output(CE_PIN, GPIO.LOW)

        if status != 0xFF:  # Si la respuesta no es 0xFF, el módulo está detectado
            print(f"✅ nRF24L01 detectado correctamente. Registro STATUS: 0x{status:02X}")
            print("⚠️ ATENCIÓN: El script no controla el estado del pin GPIO 26. "
                  "Verifique que esté correctamente conectado.")
        else:
            print("❌ No hay respuesta del nRF24L01. ¡Revisa tu cableado!")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        spi.close()  # Cerrar SPI
        GPIO.cleanup()  # Limpiar GPIO


# Run the test
if __name__ == "__main__":
    check_nrf24()
