import os
import sys
import ctypes
import pygame
import tkinter as tk

from config import *

import platform
if sys.version_info < (3, 6, 0, 'alpha', 4):
	print(f'This program requires at least Python 3.6.0a4. (You are running Python {platform.python_version()})')
	sys.exit()

if pygame.version.vernum < (2, 2, 0):
	print(f'This program requires at least Pygame 2.2.0. (You are running Pygame {pygame.version.ver})')
	sys.exit()

simu8 = ctypes.CDLL(os.path.abspath(shared_lib))

root = tk.Tk()
root.resizable(False, False)
root.title(root_w_name)
embed_pygame = tk.Frame(root, width = width, height = height)
embed_pygame.pack(side = 'top')

os.environ['SDL_WINDOWID'] = str(embed_pygame.winfo_id())
os.environ['SDL_VIDEODRIVER'] = 'windib' if os.name == 'nt' else 'x11'
pygame.display.init()
screen = pygame.display.set_mode()

interface = pygame.image.load(interface_path)
interface_rect = interface.get_rect()
status_bar = pygame.image.load(status_bar_path)
status_bar_rect = status_bar.get_rect()

ret_val = simu8.memoryInit(ctypes.c_char_p(rom_file.encode()), None)
if ret_val == 2: raise MemoryError('Unable to allocate RAM for emulated memory.')
elif ret_val == 3: raise FileNotFoundError(f'Cannot open ROM file {rom_file}. Please check the settings in config.py.')

data_mem = ctypes.c_void_p.in_dll(simu8, 'DataMemory').value

def read_mem(addr, num_bytes):
	global data_mem
	return bytes((ctypes.c_ubyte*num_bytes).from_address(data_mem + addr - rom_window_size))

def pygame_loop():
	screen.fill((0, 0, 0))

	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			simu8.coreReset()
			simu8.memoryFree()
			pygame.display.quit()
			pygame.quit()
			root.quit()
			sys.exit()

	simu8.coreStep()

	screen.blit(interface, interface_rect)

	scr_bytes = [list(read_mem(0xf000 + i*0x10, 0xc)) for i in range(0x80, 0xa0)]

	screen_data_status_bar = [
	scr_bytes[0][0] & (1 << 4),    # [S]
	scr_bytes[0][0] & (1 << 2),    # [A]
	scr_bytes[0][1] & (1 << 4),    # M
	scr_bytes[0][1] & (1 << 1),    # STO
	scr_bytes[0][2] & (1 << 6),    # RCL
	scr_bytes[0][3] & (1 << 6),    # STAT
	scr_bytes[0][4] & (1 << 7),    # CMPLX
	scr_bytes[0][5] & (1 << 6),    # MAT
	scr_bytes[0][5] & (1 << 1),    # VCT
	scr_bytes[0][7] & (1 << 5),    # [D]
	scr_bytes[0][7] & (1 << 1),    # [R]
	scr_bytes[0][8] & (1 << 4),    # [G]
	scr_bytes[0][8] & (1 << 0),    # FIX
	scr_bytes[0][9] & (1 << 5),    # SCI
	scr_bytes[0][0xa] & (1 << 6),  # Math
	scr_bytes[0][0xa] & (1 << 3),  # v
	scr_bytes[0][0xb] & (1 << 7),  # ^
	scr_bytes[0][0xb] & (1 << 4),  # Disp
	]

	screen_data = [[scr_bytes[1+i][j] & (1 << k) for j in range(0xc) for k in range(7, -1, -1)] for i in range(31)]

	for i in range(len(screen_data_status_bar)):
		if screen_data_status_bar[i]: screen.blit(status_bar, (58 + status_bar_crops[i][0], 132), status_bar_crops[i])

	for y in range(31):
		for x in range(96):
			if screen_data[y][x]: pygame.draw.rect(screen, (0, 0, 0), (58 + x*3, 144 + y*3, 3, 3))

	pygame.display.flip()
	root.update()
	root.after(0, pygame_loop)

simu8.coreReset()
pygame_loop()
tk.mainloop()
