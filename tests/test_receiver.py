# bluez_listener.py
# pip install PyBluez-updated
import bluetooth

server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
server_sock.bind(("", 1))
server_sock.listen(1)

print("Waiting for connection on RFCOMM channel 1...")
client_sock, address = server_sock.accept()
print(f"Accepted connection from {address}")

try:
    while True:
        data = client_sock.recv(1024)
        if not data:
            break
        print(f"Received: {data.decode()}")
except OSError:
    print("Disconnected.")

print("Closing sockets...")
client_sock.close()
server_sock.close()