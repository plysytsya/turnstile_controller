from pyrf24 import RF24
import time

# CE on GPIO 26, CSN on SPI CE0 (GPIO 8)
radio = RF24(26, 0)

address = b'1Node'


def setup():
    radio.begin()
    radio.setPALevel(RF24.PA_LOW)
    radio.setDataRate(RF24.BR_1MBPS)
    radio.openReadingPipe(1, address)
    radio.startListening()
    print("Receiver ready and listening...")


def listen():
    while True:
        if radio.available():
            received = []
            radio.read(received, radio.getDynamicPayloadSize())
            print("Received:", bytes(received).decode('utf-8'))
        time.sleep(0.5)


if __name__ == '__main__':
    setup()
    listen()
