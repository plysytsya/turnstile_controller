#!/usr/bin/env python3
"""
Odroid-compatible LCD display test for 16x2 I2C LCD
Works with standard PCF8574 I2C backpack
"""

import time
import smbus
from unidecode import unidecode

class LCD:
    """16x2 LCD display with I2C PCF8574 backpack"""
    
    # LCD Commands
    LCD_CLEARDISPLAY = 0x01
    LCD_RETURNHOME = 0x02
    LCD_ENTRYMODESET = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_CURSORSHIFT = 0x10
    LCD_FUNCTIONSET = 0x20
    LCD_SETCGRAMADDR = 0x40
    LCD_SETDDRAMADDR = 0x80
    
    # Entry flags
    LCD_ENTRYRIGHT = 0x00
    LCD_ENTRYLEFT = 0x02
    LCD_ENTRYSHIFTINCREMENT = 0x01
    LCD_ENTRYSHIFTDECREMENT = 0x00
    
    # Display control flags
    LCD_DISPLAYON = 0x04
    LCD_DISPLAYOFF = 0x00
    LCD_CURSORON = 0x02
    LCD_CURSOROFF = 0x00
    LCD_BLINKON = 0x01
    LCD_BLINKOFF = 0x00
    
    # Function set flags
    LCD_8BITMODE = 0x10
    LCD_4BITMODE = 0x00
    LCD_2LINE = 0x08
    LCD_1LINE = 0x00
    LCD_5x10DOTS = 0x04
    LCD_5x8DOTS = 0x00
    
    # PCF8574 pin mapping
    # P0 = RS, P1 = RW, P2 = E, P3 = Backlight, P4-P7 = Data
    RS = 0x01    # P0
    RW = 0x02    # P1  
    E  = 0x04    # P2
    BACKLIGHT = 0x08  # P3
    
    def __init__(self, bus_num=0, address=0x27):
        """Initialize LCD on specified I2C bus and address"""
        self.bus_num = bus_num
        self.address = address
        self.backlight_state = self.BACKLIGHT
        
        try:
            self.bus = smbus.SMBus(bus_num)
            self._init_lcd()
            print(f"LCD initialized on bus {bus_num}, address 0x{address:02X}")
        except Exception as e:
            print(f"Failed to initialize LCD: {e}")
            raise
    
    def _write_byte(self, data):
        """Write byte to I2C bus"""
        try:
            self.bus.write_byte(self.address, data)
        except:
            pass  # Ignore I2C errors for now
    
    def _write_nibble(self, data):
        """Write 4-bit nibble to LCD"""
        data |= self.backlight_state
        self._write_byte(data)
        self._write_byte(data | self.E)
        time.sleep(0.0005)
        self._write_byte(data & ~self.E)
        time.sleep(0.0001)
    
    def _write_byte_data(self, data, mode=0):
        """Write byte to LCD in 4-bit mode"""
        high_nibble = mode | (data & 0xF0) | self.backlight_state
        low_nibble = mode | ((data << 4) & 0xF0) | self.backlight_state
        
        self._write_nibble(high_nibble)
        self._write_nibble(low_nibble)
    
    def _init_lcd(self):
        """Initialize LCD in 4-bit mode"""
        time.sleep(0.05)  # Wait 50ms after power on
        
        # Initialize in 8-bit mode
        self._write_nibble(0x30 | self.backlight_state)
        time.sleep(0.005)
        self._write_nibble(0x30 | self.backlight_state)
        time.sleep(0.0002)
        self._write_nibble(0x30 | self.backlight_state)
        time.sleep(0.0002)
        
        # Switch to 4-bit mode
        self._write_nibble(0x20 | self.backlight_state)
        time.sleep(0.0002)
        
        # Configure LCD
        self._write_byte_data(self.LCD_FUNCTIONSET | self.LCD_4BITMODE | self.LCD_2LINE | self.LCD_5x8DOTS)
        self._write_byte_data(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)
        self.clear()
        self._write_byte_data(self.LCD_ENTRYMODESET | self.LCD_ENTRYLEFT | self.LCD_ENTRYSHIFTDECREMENT)
        time.sleep(0.002)
    
    def clear(self):
        """Clear LCD display"""
        self._write_byte_data(self.LCD_CLEARDISPLAY)
        time.sleep(0.002)
    
    def home(self):
        """Return cursor to home position"""
        self._write_byte_data(self.LCD_RETURNHOME)
        time.sleep(0.002)
    
    def set_cursor(self, col, row):
        """Set cursor position (col: 0-15, row: 0-1)"""
        row_offsets = [0x00, 0x40]
        if row >= 2:
            row = 1
        if col >= 16:
            col = 15
        self._write_byte_data(self.LCD_SETDDRAMADDR | (col + row_offsets[row]))
    
    def text(self, message, line=1):
        """Display text on specified line (1 or 2)"""
        if line == 1:
            self.set_cursor(0, 0)
        else:
            self.set_cursor(0, 1)
        
        # Pad or truncate message to 16 characters
        message = str(message)[:16].ljust(16)
        
        for char in message:
            self._write_byte_data(ord(char), self.RS)
    
    def backlight_on(self):
        """Turn backlight on"""
        self.backlight_state = self.BACKLIGHT
        self._write_byte(self.backlight_state)
    
    def backlight_off(self):
        """Turn backlight off"""  
        self.backlight_state = 0
        self._write_byte(self.backlight_state)


def display_on_lcd(line1, line2, timeout=None, bus=0, address=0x27):
    """Display text on LCD with optional scrolling"""
    try:
        lcd = LCD(bus_num=bus, address=address)
        
        max_char_count = 16
        delay = 0.5
        
        lines_to_scroll1 = scroll_text(line1, max_char_count, delay)
        lines_to_scroll2 = scroll_text(line2, max_char_count, delay)
        
        for i in range(max(len(lines_to_scroll1), len(lines_to_scroll2))):
            lcd.clear()
            lcd.text(unidecode(lines_to_scroll1[i % len(lines_to_scroll1)]), 1)
            lcd.text(unidecode(lines_to_scroll2[i % len(lines_to_scroll2)]), 2)
            time.sleep(delay)
        
        if timeout is not None:
            time.sleep(timeout - delay)
            lcd.clear()
            
    except Exception as e:
        print(f"LCD Error: {e}")


def scroll_text(line, max_char_count=16, delay=0.2):
    """Generate scrolling text frames"""
    line_length = len(line)
    if line_length <= max_char_count:
        return [line]
    
    scroll_positions = line_length - max_char_count + 1
    return [line[i:i + max_char_count] for i in range(scroll_positions)]


if __name__ == "__main__":
    print("Testing LCD on bus 0, address 0x27...")
    display_on_lcd("Hello Odroid!", "LCD Test Works!")
    
    time.sleep(2)
    
    print("Testing LCD on bus 2, address 0x30...")
    try:
        display_on_lcd("Bus 2 Test", "Address 0x30", bus=2, address=0x30)
    except:
        print("Bus 2 test failed, that's OK")