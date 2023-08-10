import os
import ast
import sys
import ctypes
import pygame
import tkinter as tk
import tkinter.ttk as ttk
import traceback

from config import *

class Data_t(ctypes.Union):
	_fields_ = [
	('raw', ctypes.c_uint64),
	('qword', ctypes.c_uint64),
	('dword', ctypes.c_uint32),
	('word', ctypes.c_uint16),
	('byte', ctypes.c_uint8),
	]

class GR_t(ctypes.Union):
	_fields_ = [
		('qrs', ctypes.c_uint64 * 2),
		('xrs', ctypes.c_uint32 * 4),
		('ers', ctypes.c_uint16 * 8),
		('rs', ctypes.c_uint8 * 16)
	]

class PSW_t_field(ctypes.Structure):
	_fields_ = [
		('ELevel', ctypes.c_uint8, 2),
		('HC', ctypes.c_uint8, 1),
		('MIE', ctypes.c_uint8, 1),
		('OV', ctypes.c_uint8, 1),
		('S', ctypes.c_uint8, 1),
		('Z', ctypes.c_uint8, 1),
		('C', ctypes.c_uint8, 1),
	]

class PSW_t(ctypes.Union):
	_fields_ = [
		('raw', ctypes.c_uint8),
		('field', PSW_t_field),
	]

import platform
if sys.version_info < (3, 6, 0, 'alpha', 4):
	print(f'This program requires at least Python 3.6.0a4. (You are running Python {platform.python_version()})')
	sys.exit()

if pygame.version.vernum < (2, 2, 0):
	print(f'This program requires at least Pygame 2.2.0. (You are running Pygame {pygame.version.ver})')
	sys.exit()

simu8 = ctypes.CDLL(os.path.abspath(shared_lib))

root = tk.Tk()
root.geometry(f'{width*(2 if debug else 1)}x{height}')
root.resizable(False, False)
root.title(root_w_name)
root['bg'] = console_bg

w_jump = tk.Toplevel(root)
w_jump.withdraw()
w_jump.geometry('250x100')
w_jump.resizable(False, False)
w_jump.title('Jump to')
w_jump.protocol('WM_DELETE_WINDOW', w_jump.withdraw)

def validate_hex(max_chars, new_char, new_str, act_code, rang = None):
	max_chars = int(max_chars)
	act_code = int(act_code)
	if rang: rang = eval(rang)

	if len(new_str) > max_chars: return False

	if act_code == 1:
		try: new_value_int = int(new_char, 16)
		except ValueError: return False
		if rang and len(new_str) == max_chars and int(new_str, 16) not in rang: return False
		else: return True
	else: return True
vh_reg = w_jump.register(validate_hex)

def get_var(var, typ): return typ.in_dll(simu8, var)

ttk.Label(w_jump, text = 'Input new values for CSR and PC.\n(please input hex bytes)', justify = 'center').pack()

jump_csr = tk.Frame(w_jump); jump_csr.pack(fill = 'x')
ttk.Label(jump_csr, text = 'CSR').pack(side = 'left')
jump_csr_entry = ttk.Entry(jump_csr, validate = 'key', validatecommand = (vh_reg, 1, '%S', '%P', '%d')); jump_csr_entry.pack(side = 'right')
jump_csr_entry.insert(0, '0')

jump_pc = tk.Frame(w_jump); jump_pc.pack(fill = 'x')
ttk.Label(jump_pc, text = 'PC').pack(side = 'left')
jump_pc_entry = ttk.Entry(jump_pc, validate = 'key', validatecommand = (vh_reg, 4, '%S', '%P', '%d', range(0, 0xfffe, 2))); jump_pc_entry.pack(side = 'right')

died = False
def set_csr_pc():
	get_var('CSR', ctypes.c_uint8).value = int(jump_csr_entry.get(), 16)
	get_var('PC', ctypes.c_uint16).value = int(jump_pc_entry.get(), 16)
	died = False
	w_jump.withdraw()

	jump_csr_entry.delete(0, 'end'); jump_csr_entry.insert(0, '0')
	jump_pc_entry.delete(0, 'end')

ttk.Button(w_jump, text = 'OK', command = set_csr_pc).pack(side = 'bottom')

rc_menu = tk.Menu(tearoff = 0)
rc_menu.add_command(label = 'Jump to...', accelerator = 'J', command = w_jump.deiconify)

def open_popup(x):
	try: rc_menu.tk_popup(x.x_root, x.y_root)
	finally: rc_menu.grab_release()

root.bind('<Button-3>', open_popup)
root.bind('j', lambda x: w_jump.deiconify())
root.bind('J', lambda x: w_jump.deiconify())

embed_pygame = tk.Frame(root, width = width, height = height)
embed_pygame.pack(side = 'left')

if debug:
	info_label = tk.Label(root, text = 'No text loaded yet.', width = width, height = height, font = ('Consolas', console_size), fg = console_fg, bg = console_bg, justify = 'left', anchor = 'nw')
	info_label.pack(side = 'left')

os.environ['SDL_WINDOWID'] = str(embed_pygame.winfo_id())
os.environ['SDL_VIDEODRIVER'] = 'windib' if os.name == 'nt' else 'x11'
pygame.init()
pygame.display.init()
screen = pygame.display.set_mode()


interface = pygame.image.load(interface_path)
interface_rect = interface.get_rect()
status_bar = pygame.image.load(status_bar_path)
status_bar_rect = status_bar.get_rect()
died_text = pygame.font.SysFont('Consolas', int(console_size * 1.5)).render('Died', True, console_fg)
died_text_rect = died_text.get_rect()
died_text_rect.center = (width // 2, height // 2)

ret_val = simu8.memoryInit(ctypes.c_char_p(rom_file.encode()), None)
if ret_val == 2: raise MemoryError('Unable to allocate RAM for emulated memory.')
elif ret_val == 3: raise FileNotFoundError(f'Cannot open the ROM file {rom_file}. If the file exists, please check the settings in config.py.')



def split_num(num):
	if num <= 0: return []

	result = []
	for i in (8, 4, 2, 1):
		while num >= i:
			result.append(i)
			num -= i

	return result

def read_dmem(addr, num_bytes, segment = 0):
	data = b''
	bytes_retrieved = 0

	for i in split_num(num_bytes):
		simu8.memoryGetData(ctypes.c_uint8(segment), ctypes.c_uint16(addr + bytes_retrieved), ctypes.c_size_t(i))
		dt = get_var('DataRaw', Data_t)
		if i == 8: dt_ = dt.qword
		elif i == 4: dt_ = dt.dword
		elif i == 2: dt_ = dt.word
		elif i == 1: dt_ = dt.byte
		data += dt_.to_bytes(i, 'big')
		bytes_retrieved += i

	return data


def exit_sim():
	simu8.coreReset()
	simu8.memoryFree()
	pygame.display.quit()
	pygame.quit()
	root.quit()
	sys.exit()

def pygame_loop():
	global died

	screen.fill((0, 0, 0))

	for event in pygame.event.get():
		if event.type == pygame.QUIT: exit_sim()

	if not died:
		ret_val = simu8.coreStep()
		if debug:
			gr = get_var('GR', GR_t)
			csr = get_var('CSR', ctypes.c_uint8).value
			pc = get_var('PC', ctypes.c_uint16).value
			sp = get_var('SP', ctypes.c_uint16).value
			info_label['text'] = f'''\
=== REGISTERS ===

General registers:
QR0 = ''' + ' '.join(f'{(gr.qrs[0] >> (i*8)) & 0xff:02X}' for i in range(8)) + f'''
QR8 = ''' + ' '.join(f'{(gr.qrs[1] >> (i*8)) & 0xff:02X}' for i in range(8)) + f'''

Control registers:
CSR:PC               {csr:02X}:{pc:04X}H
Code words @ CSR:PC  {ctypes.c_uint16.from_address(get_var('CodeMemory', ctypes.c_void_p).value + csr*0x10000 + pc).value:04X} {ctypes.c_uint16.from_address(get_var('CodeMemory', ctypes.c_void_p).value + csr*0x10000 + pc + 2).value:04X}
SP                   {sp:04X}H
DWORDs @ SP          ''' + ' '.join(f'{int.from_bytes(read_dmem(sp + i, 4), "big"):08X}' for i in range(0, 8, 4)) + f'''
({sp:04X}H - {sp + 15:04X}H)      ''' + ' '.join(f'{int.from_bytes(read_dmem(sp + i, 4), "big"):08X}' for i in range(8, 16, 4)) + f'''
DSR:EA               {get_var('DSR', ctypes.c_uint8).value:01X}:{get_var('EA', ctypes.c_uint16).value:04X}H
PSW                  {get_var('PSW', PSW_t).raw:02X}  {get_var('PSW', PSW_t).raw:08b}


LCSR:LR              {get_var('LCSR', ctypes.c_uint8).value:02X}:{get_var('LR', ctypes.c_uint16).value:04X}H
ECSR1:ELR1           {get_var('ECSR1', ctypes.c_uint8).value:02X}:{get_var('ELR1', ctypes.c_uint16).value:04X}H
ECSR2:ELR2           {get_var('ECSR2', ctypes.c_uint8).value:02X}:{get_var('ELR2', ctypes.c_uint16).value:04X}H
ECSR3:ELR3           {get_var('ECSR3', ctypes.c_uint8).value:02X}:{get_var('ELR3', ctypes.c_uint16).value:04X}H

EPSW1                {get_var('EPSW1', PSW_t).raw:02X}
EPSW2                {get_var('EPSW2', PSW_t).raw:02X}
EPSW3                {get_var('EPSW3', PSW_t).raw:02X}
'''
		if ret_val == 3:
			print('DIED: Illegal instruction found')
			died = True
		if ret_val == 1: print(f'WARNING: Write to read-only region @ CSR:PC = {get_var("CSR", ctypes.c_uint8).value:02X}:{get_var("PC", ctypes.c_uint16).value:04X}H')
		if ret_val == 2: print(f'WARNING: Unimplemented instruction skipped @ address {get_var("CSR", ctypes.c_uint8).value:01X}{(get_var("PC", ctypes.c_uint16).value - 2) & 0xffff:04X}H')

	if not died:
		screen.blit(interface, interface_rect)

		scr_bytes = [list(read_dmem(0xf000 + i*0x10, 0xc)) for i in range(0x80, 0xa0)]

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

		screen_data = [[scr_bytes[1+i][j] & (1 << k) for j in range(0xc) for k in range(8)] for i in range(31)]

		for i in range(len(screen_data_status_bar)):
			if screen_data_status_bar[i]: screen.blit(status_bar, (58 + status_bar_crops[i][0], 132), status_bar_crops[i])

		for y in range(31):
			for x in range(96):
				if screen_data[y][x]: pygame.draw.rect(screen, (0, 0, 0), (58 + x*3, 144 + y*3, 3, 3))
	else:
		screen.fill(console_bg)
		screen.blit(died_text, died_text_rect)

	pygame.display.update()
	root.update()
	root.after(0, pygame_loop)

simu8.coreReset()
pygame_loop()
tk.mainloop()
