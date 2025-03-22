import paho.mqtt.client as mqtt

# Callback when the client receives a connection acknowledgment from the broker
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("home/raspberry")

# Callback for when a PUBLISH message is received from the server
def on_message(client, userdata, msg):
    print(f"Topic: {msg.topic} | Message: {msg.payload.decode()}")

client = mqtt.Client()
client.username_pw_set("your_username", "your_password")
client.on_connect = on_connect
client.on_message = on_message

# Replace '192.168.1.10' with the IP address of your MQTT broker
client.connect("127.0.0.1", 1883, 60)
client.loop_forever()