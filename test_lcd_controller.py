from lcd_controller import LCDController
import threading

LCD27 = LCDController(use_lcd=True, lcd_address=0x27)
LCD20 = LCDController(use_lcd=True, lcd_address=0x20)

def display_on_lcd20():
    LCD20.display("hello1", "line2-1", timeout=10)

def display_on_lcd27():
    LCD27.display("hello2", "line2-2", timeout=10)

def main():
    thread_lcd20 = threading.Thread(target=display_on_lcd20)
    thread_lcd27 = threading.Thread(target=display_on_lcd27)

    thread_lcd20.start()
    thread_lcd27.start()

    thread_lcd20.join()
    thread_lcd27.join()


if __name__ == "__main__":
    main()
