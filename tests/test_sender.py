# bluez_auto_sender.py
# pip install PyBluez-updated
import bluetooth
import time

server_mac = 'B8:27:EB:A0:7E:6D'  # Replace with your server Pi's MAC
port = 1

sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
sock.connect((server_mac, port))
print("Connected to server. Sending messages every 2 seconds...")

try:
    counter = 0
    while True:
        message = f"Hello {counter}"
        sock.send(message)
        print(f"Sent: {message}")
        counter += 1
        time.sleep(2)
except KeyboardInterrupt:
    print("\nStopped.")

sock.close()
