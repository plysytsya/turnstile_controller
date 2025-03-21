from pyrf24 import RF24, RF24_PA_LOW, RF24_1MBPS
import time

# CE = GPIO26, CSN = SPI0_CE0
radio = RF24(26, 0)
address = b"1Node"

def setup():
    radio.begin()
    radio.setPALevel(RF24_PA_LOW)
    radio.setDataRate(RF24_1MBPS)
    radio.openReadingPipe(1, address)
    radio.startListening()
    print("Receiver ready and listening...")

def listen():
    while True:
        if radio.available():
            buffer = bytearray(32)
            length = radio.read(buffer)
            print("Received:", buffer[:length].decode('utf-8'))
        time.sleep(0.5)

if __name__ == '__main__':
    setup()
    listen()