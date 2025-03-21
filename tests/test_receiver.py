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
            payload = radio.read()
            print("Received:", payload.decode('utf-8').strip('\x00'))
        time.sleep(0.5)

if __name__ == '__main__':
    setup()
    listen()