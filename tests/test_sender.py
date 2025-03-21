#!/usr/bin/env python
import time
from nrf24 import NRF24
import RPi.GPIO as GPIO

# Define two pipes (addresses) as lists of 5 integers each.
pipes = [[0xe7, 0xe7, 0xe7, 0xe7, 0xe7],  # Writing pipe address
         [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]]  # Reading pipe address (for ACKs)

radio = NRF24()

def setup():
    # Initialize the radio: SPI bus 0, CE pin 26.
    radio.begin(0, 26)
    radio.setPayloadSize(32)         # Use fixed payload size of 32 bytes
    radio.setChannel(0x76)             # Set an RF channel (example: 0x76)
    radio.setDataRate(NRF24.BR_1MBPS)  # Set data rate to 1 MBPS
    radio.setPALevel(NRF24.PA_LOW)     # Set power amplifier level to low
    radio.openWritingPipe(pipes[0])
    radio.stopListening()            # Stop listening to become a transmitter
    radio.printDetails()             # Print configuration details for debugging
    print("Sender ready.")

def send_message(message):
    # Convert the message to a list of ASCII values and pad it to 32 bytes.
    data = list(message.encode('utf-8'))
    while len(data) < 32:
        data.append(0)
    result = radio.write(data)
    if result:
        print("Sent: {}".format(message))
    else:
        print("Send failed")

if __name__ == '__main__':
    setup()
    while True:
        send_message("Hello from sender!")
        time.sleep(1)
