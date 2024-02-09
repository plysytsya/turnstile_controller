from rpi_lcd import LCD

# Initialize the LCD
lcd = LCD()


def display_restarting_message():
    lcd.clear()
    lcd.text("Reiniciando...", 1)
    lcd.text("Espera por favor", 2)


if __name__ == "__main__":
    try:
        display_restarting_message()
    except KeyboardInterrupt:
        lcd.clear()
