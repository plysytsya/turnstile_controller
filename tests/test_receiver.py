import RF24
import time

import struct

pipes = [0x52, 0x78, 0x41, 0x41, 0x41]
pipesbytes = bytearray(pipes)

radio = RF24.RF24()
radio.begin(25, 0)  # Set CE and IRQ pins
radio.setPALevel(RF24.RF24_PA_MAX)
radio.setDataRate(RF24.RF24_250KBPS)
radio.setChannel(0x4c)
radio.openReadingPipe(1, pipesbytes)
radio.startListening()
radio.printDetails()

# radio.powerUp()
cont = 0

while True:
    pipe = [1]

    while not radio.available():
        time.sleep(0.250)

    recv_buffer = bytearray([])
    recv_buffer = radio.read(32)
    print(recv_buffer)