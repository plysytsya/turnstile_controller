from pyrf24 import RF24, RF24_PA_LOW, RF24_1MBPS
import time

# CE on GPIO 26, CSN on SPI CE0 (GPIO 8)
radio = RF24(26, 0)

address = b'1Node'

def setup():
    if not radio.begin():
        raise RuntimeError("radio hardware is not responding")
    radio.setPALevel(RF24_PA_LOW)
    radio.setDataRate(RF24_1MBPS)
    radio.openWritingPipe(address)
    radio.stopListening()
    print("Sender ready.")

def send_message(message):
    result = radio.write(message.encode('utf-8'))
    if result:
        print(f"Sent: {message}")
    else:
        print("Send failed")

if __name__ == '__main__':
    setup()
    while True:
        send_message("Hello Pi Receiver!")
        time.sleep(10)