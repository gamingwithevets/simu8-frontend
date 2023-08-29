# Configuration file for SimU8 frontend

# Path to the shared library.
shared_lib = 'simu8.so'

# Path to the ROM file.
rom_file = 'rom.bin'

# Path to the status bar image.
status_bar_path = 'images/interface_es_bar.png'

# Path to the interface image.
interface_path = 'images/interface_esp_991esp.png'

# Settings for the Tkinter window.

# Width and height of the Pygame embed widget.
width = 405
height = 816

# Name of the Tkinter window.
root_w_name = 'fx-570ES PLUS Emulator'

# "Console" text font.
console_font = ('Consolas', 11)

# "Console" background color.
console_bg = '#0c0c0c'

# "Console" text color.
console_fg = '#cccccc'

# Pygame text color.
pygame_color = (0, 0, 0)

# Hex display window size.
data_mem_width = 700
data_mem_height = 600

# Hex display text font.
data_mem_font = ('Courier New', 11)

# The settings below should work out of the box for ES and ES PLUS ROMs.
# Only modify if you know what you're doing.

# Crop areas of the status bar.
status_bar_crops = (
(0, 0, 8, 10),     # [S]
(9, 0, 9, 10),     # [A]
(21, 0, 8, 9),     # M
(21, 0, 8, 9),     # STO
(32, 0, 17, 10),   # RCL
(50, 0, 17, 10),   # STAT
(70, 0, 21, 10),   # CMPLX
(91, 0, 32, 10),   # MAT
(123, 0, 36, 10),  # VCT
(161, 0, 9, 10),   # [D]
(170, 0, 9, 10),   # [R] 
(180, 0, 9, 10),   # [G]
(192, 0, 14, 9),   # FIX
(206, 0, 14, 10),  # SCI
(224, 0, 23, 10),  # Math
(249, 0, 9, 9),    # v
(258, 0, 9, 9),    # ^
(268, 0, 19, 11),  # Disp
)

# Keymaps for the keyboard.
# None = core reset

keymap_mouse = {
	# (left, top, width, height): (ki, ko)
	(41,  293, 48, 38): (7, 0),
	(95,  301, 48, 38): (7, 1),
	(262, 301, 48, 38): (7, 4),
	(316, 293, 48, 38): None,
}

keymap_kb = {
	# keysym: (ki, ko)
	'f1': (7, 0),
	'f2': (7, 1),
	'up': (7, 2),
	'right': (7, 3),
	'f3': (7, 4),
	'home': (7, 4),
	'f4': None,
	'f5': (6, 0),
	'f6': (6, 1),
	'left': (6, 2),
	'down': (6, 3),
	'f7': (6, 4),
	'parenleft': (3, 2),
	'parenright': (3, 3),
	'7': (2, 0),
	'8': (2, 1),
	'9': (2, 2),
	'backspace': (2, 3),
	'space': (2, 4),
	'tab': (2, 4),
	'4': (1, 0),
	'5': (1, 1),
	'6': (1, 2),
	'asterisk': (1, 3),
	'slash': (1, 4),
	'1': (0, 0),
	'2': (0, 1),
	'3': (0, 2),
	'plus': (0, 3),
	'minus': (0, 4),
	'0': (4, 6),
	'period': (3, 6),
	'e': (2, 6),
	'return': (0, 6),
}

# Date and time format for logging module.
dt_format = '%d/%m/%Y %H:%M:%S'
