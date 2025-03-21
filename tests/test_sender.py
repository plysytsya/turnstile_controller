from pyrf24 import RF24
import time

# CE on GPIO 26, CSN on SPI CE0 (GPIO 8)
radio = RF24(26, 0)

address = b'1Node'


def setup():
    radio.begin()
    radio.setPALevel(RF24.PA_LOW)
    radio.setDataRate(RF24.BR_1MBPS)
    radio.setRetries(5, 15)
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
        time.sleep(1)
