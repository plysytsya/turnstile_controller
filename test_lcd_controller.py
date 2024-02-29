# lcd_controller_test.py

from lcd_controller import LCDController

LCD27 = LCDController(use_lcd=True, lcd_address=0x27)
LCD20 = LCDController(use_lcd=True, lcd_address=0x20)


def main():
    LCD20.display("hello1", "line2-1", timeout=2)
    LCD27.display("hello2", "line2-2", timeout=2)


if __name__ == "__main__":
    main()
