from py532lib.i2c import *
from py532lib.frame import *
from py532lib.constants import *
import time

# Initialize PN532 over I2C
pn532 = Pn532_i2c()
pn532.SAMconfigure()


def convert_uid_to_decimal(card_data):
    # Use only the last 4 bytes of the card UID and reverse (little-endian)
    last_four_bytes = card_data[-4:][::-1]

    # Convert these 4 bytes to a hexadecimal string
    hex_string = "".join([f"{byte:02X}" for byte in last_four_bytes])

    # Convert the hex string to a decimal integer
    decimal_value = int(hex_string, 16)

    return decimal_value


# Continuous scanning loop
while True:
    # Scan for RFID/NFC cards
    card_data = pn532.read_mifare().get_data()

    if card_data:
        # Convert the last 4 bytes of the card data to a decimal value
        card_uid_decimal = convert_uid_to_decimal(card_data)

        # Format the decimal number to be exactly 10 digits long
        formatted_uid = f"{card_uid_decimal:010d}"
        print(f"Card UID (Decimal): {formatted_uid}")
    else:
        print("No card detected.")

    time.sleep(1)
