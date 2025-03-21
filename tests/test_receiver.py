import time
import pigpio
from nrf24 import NRF24

pi = pigpio.pi()
if not pi.connected:
    raise IOError("Can't connect to pigpio daemon!")

radio = NRF24(pi, ce=26)
radio.set_address_bytes(5)
radio.set_channel(76)
radio.set_data_rate("1MBPS")  # ✅ Use string, not constant
radio.set_pa_level("LOW")     # ✅ Same here
radio.open_reading_pipe(1, b"1Node")
radio.start_listening()

print("Receiver ready.")

while True:
    if radio.available():
        pipe = radio.rx_pipe()
        payload = radio.read()
        print("Received:", payload.decode('utf-8').strip('\x00'))
    time.sleep(0.1)