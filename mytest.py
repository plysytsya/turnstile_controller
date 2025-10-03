# mytest.py  (libgpiod v1.x)
import gpiod

CHIP   = "gpiochip0"
OFFSET = 62           # header pin 7 (GPIOA_13)
ACTIVE_LOW = True     # many 3-pin relay boards click on LOW

line = gpiod.Chip(CHIP).get_line(OFFSET)
line.request(consumer="relay", type=gpiod.LINE_REQ_DIR_OUT)

# define logic levels
OFF = 1 if ACTIVE_LOW else 0
ON  = 0 if ACTIVE_LOW else 1

# ensure OFF to start
line.set_value(OFF)
state = OFF

try:
    while True:
        input("Press ENTER to toggle relay...")
        state = ON if state == OFF else OFF
        line.set_value(state)
        print("Relay is now", "ON" if state == ON else "OFF",
              "(LOW=ON)" if ACTIVE_LOW else "(HIGH=ON)")
except KeyboardInterrupt:
    pass
finally:
    line.set_value(OFF)
    line.release()
