import paho.mqtt.client as mqtt
import time

client = mqtt.Client()
client.connect("fmscamara.local", 1883, 60)

while True:
    client.publish("home/raspberry", "Hello from Raspberry Pi!")
    time.sleep(5)


"""
install mqtt broker

sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

update the configuration file

sudo nano /etc/mosquitto/mosquitto.conf

#######
# Place your local configuration in /etc/mosquitto/conf.d/
#
# A full description of the configuration file is at
# /usr/share/doc/mosquitto/examples/mosquitto.conf.example

pid_file /run/mosquitto/mosquitto.pid

persistence true
persistence_location /var/lib/mosquitto/

log_dest file /var/log/mosquitto/mosquitto.log

include_dir /etc/mosquitto/conf.d

listener 1883 0.0.0.0

allow_anonymous true
#######
sudo systemctl restart mosquitto

install paho-mqtt==2.1.0
"""