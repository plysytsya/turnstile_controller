# lcd_controller_test.py

from lcd_controller import LCDController

LCD25 = LCDController(use_lcd=True, lcd_address=25)
LCD27 = LCDController(use_lcd=True, lcd_address=27)


def main():
    LCD25.display("hello1", "line2-1", timeout=2)
    LCD27.display("hello2", "line2-2", timeout=2)


if __name__ == "__main__":
    main()
