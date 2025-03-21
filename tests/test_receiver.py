import time
import pigpio
from nrf24 import NRF24, RF24_DATA_RATE, RF24_PA

pi = pigpio.pi()
if not pi.connected:
    raise IOError("Can't connect to pigpio daemon!")

radio = NRF24(pi, ce=26)
radio.set_address_bytes(5)
radio.set_channel(76)
radio.set_data_rate(RF24_DATA_RATE.RATE_1MBPS)
radio.set_pa_level(RF24_PA.LOW)
radio.open_reading_pipe(1, b"1Node")
radio.start_listening()

print("Receiver ready.")

while True:
    if radio.available():
        pipe = radio.rx_pipe()
        payload = radio.read()
        print("Received:", payload.decode('utf-8').strip('\x00'))
    time.sleep(0.1)