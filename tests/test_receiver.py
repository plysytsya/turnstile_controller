#!/usr/bin/env python
import time
from nrf24 import NRF24
import RPi.GPIO as GPIO

# Use the same pipe addresses as in the sender.
pipes = [[0xe7, 0xe7, 0xe7, 0xe7, 0xe7],  # (not used in RX mode)
         [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]]  # Reading pipe address

radio = NRF24()

def setup():
    # Initialize the radio on SPI bus 0 with CE on GPIO26.
    radio.begin(0, 26)
    radio.setPayloadSize(32)
    radio.setChannel(0x76)
    radio.setDataRate(NRF24.BR_1MBPS)
    radio.setPALevel(NRF24.PA_LOW)
    radio.openReadingPipe(1, pipes[1])
    radio.startListening()           # Start listening for incoming data
    radio.printDetails()             # Print configuration details for debugging
    print("Receiver ready.")

def listen():
    while True:
        if radio.available():
            received_message = []
            # Read the payload (32 bytes).
            radio.read(received_message, radio.getPayloadSize())
            # Convert the list of integers to a string, ignoring padding zeros.
            message = "".join(chr(i) for i in received_message if i != 0)
            print("Received: {}".format(message))
        time.sleep(0.1)

if __name__ == '__main__':
    setup()
    listen()