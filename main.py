import os
import ast
import sys
import ctypes
import pygame
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox
import traceback
import logging

from config import *

logging.basicConfig(datefmt = dt_format, format = '[%(asctime)s] %(levelname)s: %(message)s')

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

# https://stackoverflow.com/a/16198198
class VerticalScrolledFrame(tk.Frame):
	def __init__(self, parent, *args, **kw):
		tk.Frame.__init__(self, parent, *args, **kw)

		vscrollbar = tk.Scrollbar(self, orient = 'vertical')
		vscrollbar.pack(fill = 'y', side = 'right')
		canvas = tk.Canvas(self, bd = 0, highlightthickness = 0, yscrollcommand = vscrollbar.set)
		canvas.pack(side = 'left', fill = 'both', expand = True)
		vscrollbar.config(command = canvas.yview)

		canvas.xview_moveto(0)
		canvas.yview_moveto(0)

		self.interior = interior = tk.Frame(canvas)
		interior_id = canvas.create_window(0, 0, window = interior, anchor = 'nw')

		def _configure_interior(event):
			size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
			canvas.config(scrollregion = '0 0 %s %s' % size)
			if interior.winfo_reqwidth() != canvas.winfo_width():
				canvas.config(width=interior.winfo_reqwidth())
		interior.bind('<Configure>', _configure_interior)

		def _configure_canvas(event):
			if interior.winfo_reqwidth() != canvas.winfo_width():
				canvas.itemconfigure(interior_id, width=canvas.winfo_width())
		canvas.bind('<Configure>', _configure_canvas)

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

def get_var(var, typ): return typ.in_dll(simu8, var)

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

def read_cmem(addr, segment = 0):
	simu8.memoryGetCodeWord(ctypes.c_uint8(segment), ctypes.c_uint16(addr))
	return get_var('CodeWord', ctypes.c_uint16).value

def calc_checksum():
	csum = 0
	for i in range(0, 0xfffe, 2):
		cword = read_cmem(i, 8)
		csum += ((cword & 0xff00) >> 8) | ((cword & 0xff) << 8)

	for i in range(0, 0xfffa, 2):
		cword = read_cmem(i, 1)
		csum += ((cword & 0xff00) >> 8) | ((cword & 0xff) << 8)

	tk.messagebox.showinfo('Checksum', f'Expected checksum: {read_cmem(0xfffc, 1):04X}\nCalculated checksum: {csum % 0x10000:04X}')

def set_csr_pc():
	get_var('CSR', ctypes.c_uint8).value = int(jump_csr_entry.get(), 16)
	get_var('PC', ctypes.c_uint16).value = int(jump_pc_entry.get(), 16)
	print_regs()
	w_jump.withdraw()

	jump_csr_entry.delete(0, 'end'); jump_csr_entry.insert(0, '0')
	jump_pc_entry.delete(0, 'end')

def show_mem():
	if not single_step:
		tk.messagebox.showerror('Single-step mode required', 'This function requires single-step mode.')
		return

def get_mem():
	data = 

def set_brkpoint():
	global brkpoint

	brkpoint = (int(brkpoint_csr_entry.get(), 16) << 16) + int(brkpoint_pc_entry.get(), 16)
	print_regs()
	w_brkpoint.withdraw()

	brkpoint_csr_entry.delete(0, 'end'); brkpoint_csr_entry.insert(0, '0')
	brkpoint_pc_entry.delete(0, 'end')

def clear_brkpoint():
	global brkpoint
	brkpoint = None
	print_regs()

def set_step():
	global step
	step = True

def set_single_step(val):
	global single_step, info_label
	single_step = val
	step_bt['state'] = 'normal' if val else 'disabled'

def open_popup(x):
	try: rc_menu.tk_popup(x.x_root, x.y_root)
	finally: rc_menu.grab_release()

def print_regs():
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
CSR:PC                 {csr:02X}:{pc:04X}H
Code words @ CSR:PC    {read_cmem(pc, csr):04X} {read_cmem(pc + 2, csr):04X} {read_cmem(pc + 4, csr):04X}
SP                     {sp:04X}H
Words at SP            ''' + ' '.join(format(int.from_bytes(read_dmem(sp + i, 2), 'big'), '04X') for i in range(0, 8, 2)) + f'''
                       ''' + ' '.join(format(int.from_bytes(read_dmem(sp + i, 2), 'big'), '04X') for i in range(8, 16, 2)) + f'''
No. of words in stack  {(sp_start - sp) // 2 if sp_start - sp >= 0 else '[Stack underflow!]'}
DSR:EA                 {get_var('DSR', ctypes.c_uint8).value:01X}:{get_var('EA', ctypes.c_uint16).value:04X}H
PSW                    {get_var('PSW', PSW_t).raw:02X}  {get_var('PSW', PSW_t).raw:08b}


LCSR:LR                {get_var('LCSR', ctypes.c_uint8).value:02X}:{get_var('LR', ctypes.c_uint16).value:04X}H
ECSR1:ELR1             {get_var('ECSR1', ctypes.c_uint8).value:02X}:{get_var('ELR1', ctypes.c_uint16).value:04X}H
ECSR2:ELR2             {get_var('ECSR2', ctypes.c_uint8).value:02X}:{get_var('ELR2', ctypes.c_uint16).value:04X}H
ECSR3:ELR3             {get_var('ECSR3', ctypes.c_uint8).value:02X}:{get_var('ELR3', ctypes.c_uint16).value:04X}H

EPSW1                  {get_var('EPSW1', PSW_t).raw:02X}
EPSW2                  {get_var('EPSW2', PSW_t).raw:02X}
EPSW3                  {get_var('EPSW3', PSW_t).raw:02X}

{'Breakpoint set to ' + format(brkpoint >> 16, '02X') + ':' + format(brkpoint % 0x10000, '04X') + 'H' if brkpoint is not None else 'No breakpoint set.'}
'''

def reset_core():
	simu8.coreReset()
	print_regs()

def exit_sim():
	simu8.coreReset()
	simu8.memoryFree()
	pygame.display.quit()
	pygame.quit()
	root.quit()
	sys.exit()

import platform
if sys.version_info < (3, 6, 0, 'alpha', 4):
	print(f'This program requires at least Python 3.6.0a4. (You are running Python {platform.python_version()})')
	sys.exit()

if pygame.version.vernum < (2, 2, 0):
	print(f'This program requires at least Pygame 2.2.0. (You are running Pygame {pygame.version.ver})')
	sys.exit()

simu8 = ctypes.CDLL(os.path.abspath(shared_lib))

root = tk.Tk()
root.geometry(f'{width*2}x{height}')
root.resizable(False, False)
root.title(root_w_name)
root.focus_set()
root['bg'] = console_bg

w_jump = tk.Toplevel(root)
w_jump.withdraw()
w_jump.geometry('250x100')
w_jump.resizable(False, False)
w_jump.title('Jump to address')
w_jump.protocol('WM_DELETE_WINDOW', w_jump.withdraw)
w_jump_vh_reg = w_jump.register(validate_hex)
ttk.Label(w_jump, text = 'Input new values for CSR and PC.\n(please input hex bytes)', justify = 'center').pack()
jump_csr = tk.Frame(w_jump); jump_csr.pack(fill = 'x')
ttk.Label(jump_csr, text = 'CSR').pack(side = 'left')
jump_csr_entry = ttk.Entry(jump_csr, validate = 'key', validatecommand = (w_jump_vh_reg, 2, '%S', '%P', '%d')); jump_csr_entry.pack(side = 'right')
jump_csr_entry.insert(0, '0')
jump_pc = tk.Frame(w_jump); jump_pc.pack(fill = 'x')
ttk.Label(jump_pc, text = 'PC').pack(side = 'left')
jump_pc_entry = ttk.Entry(jump_pc, validate = 'key', validatecommand = (w_jump_vh_reg, 4, '%S', '%P', '%d', range(0, 0xfffe, 2))); jump_pc_entry.pack(side = 'right')
ttk.Button(w_jump, text = 'OK', command = set_csr_pc).pack(side = 'bottom')
w_jump.bind('<Return>', lambda x: set_csr_pc())
w_jump.bind('<Escape>', lambda x: w_jump.withdraw())

w_brkpoint = tk.Toplevel(root)
w_brkpoint.withdraw()
w_brkpoint.geometry('300x125')
w_brkpoint.resizable(False, False)
w_brkpoint.title('Set breakpoint')
w_brkpoint.protocol('WM_DELETE_WINDOW', w_brkpoint.withdraw)
w_brkpoint_vh_reg = w_brkpoint.register(validate_hex)
ttk.Label(w_brkpoint, text = 'Single-step mode will be activated if CSR:PC matches\nthe below. Note that only 1 breakpoint can be set.\n(please input hex bytes)', justify = 'center').pack()
brkpoint_csr = tk.Frame(w_brkpoint); brkpoint_csr.pack(fill = 'x')
ttk.Label(brkpoint_csr, text = 'CSR').pack(side = 'left')
brkpoint_csr_entry = ttk.Entry(brkpoint_csr, validate = 'key', validatecommand = (w_brkpoint_vh_reg, 2, '%S', '%P', '%d')); brkpoint_csr_entry.pack(side = 'right')
brkpoint_csr_entry.insert(0, '0')
brkpoint_pc = tk.Frame(w_brkpoint); brkpoint_pc.pack(fill = 'x')
ttk.Label(brkpoint_pc, text = 'PC').pack(side = 'left')
brkpoint_pc_entry = ttk.Entry(brkpoint_pc, validate = 'key', validatecommand = (w_brkpoint_vh_reg, 4, '%S', '%P', '%d', range(0, 0xfffe, 2))); brkpoint_pc_entry.pack(side = 'right')
ttk.Button(w_brkpoint, text = 'OK', command = set_brkpoint).pack(side = 'bottom')
w_brkpoint.bind('<Return>', lambda x: set_brkpoint())
w_brkpoint.bind('<Escape>', lambda x: w_brkpoint.withdraw())

w_data_mem = tk.Toplevel(root)
w_data_mem.withdraw()
w_data_mem.geometry('600x600')
w_data_mem.resizable(False, False)
w_data_mem.title('Show data memory')
w_data_mem.protocol('WM_DELETE_WINDOW', w_data_mem.withdraw)
segment_cb = ttk.Combobox(w_data_mem)
segment_cb.pack()

embed_pygame = tk.Frame(root, width = width, height = height)
embed_pygame.pack(side = 'left')

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

ret_val = simu8.memoryInit(ctypes.c_char_p(rom_file.encode()), None)
if ret_val == 2:
	logging.error('Unable to allocate RAM for emulated memory.')
	sys.exit(-1)
elif ret_val == 3:
	logging.error(f'Cannot open the ROM file {rom_file}. If the file exists, please check the settings in config.py.')
	sys.exit(-1)

single_step = True
step = False
brkpoint = None
sp_start = read_cmem(0)

rc_menu = tk.Menu(root, tearoff = 0)
rc_menu.add_command(label = 'Enable single-step mode', accelerator = 'S', command = lambda: set_single_step(True))
rc_menu.add_command(label = 'Resume execution', accelerator = 'P', command = lambda: set_single_step(False))
rc_menu.add_separator()
rc_menu.add_command(label = 'Jump to...', accelerator = 'J', command = w_jump.deiconify)
rc_menu.add_separator()
rc_menu.add_command(label = 'Set breakpoint to...', accelerator = 'B', command = w_brkpoint.deiconify)
rc_menu.add_command(label = 'Clear breakpoint', accelerator = 'N', command = clear_brkpoint)
rc_menu.add_separator()
rc_menu.add_command(label = 'Reset core', accelerator = 'C', command = reset_core)
rc_menu.add_separator()

extra_funcs = tk.Menu(rc_menu, tearoff = 0)
extra_funcs.add_command(label = 'Calculate checksum', command = calc_checksum)
rc_menu.add_cascade(label = 'Extra functions', menu = extra_funcs)

root.bind('<Button-3>', open_popup)
root.bind('s', lambda x: set_single_step(True)); root.bind('S', lambda x: set_single_step(True))
root.bind('p', lambda x: set_single_step(False)); root.bind('P', lambda x: set_single_step(False))
root.bind('j', lambda x: w_jump.deiconify()); root.bind('J', lambda x: w_jump.deiconify())
root.bind('b', lambda x: w_brkpoint.deiconify()); root.bind('B', lambda x: w_brkpoint.deiconify())
root.bind('n', lambda x: clear_brkpoint()); root.bind('N', lambda x: clear_brkpoint())
root.bind('c', lambda x: reset_core()); root.bind('C', lambda x: reset_core())

def pygame_loop():
	global single_step, step, brkpoint

	screen.fill((0, 0, 0))

	for event in pygame.event.get():
		if event.type == pygame.QUIT: exit_sim()

	if (single_step and step) or not single_step:
		ret_val = simu8.coreStep()
		csr = get_var('CSR', ctypes.c_uint8).value
		pc = get_var('PC', ctypes.c_uint16).value
		if (csr << 16) + pc == brkpoint:
			tk.messagebox.showinfo('Breakpoint hit!', f'Breakpoint {csr:02X}:{pc:04X}H has been hit!')
			set_single_step(True)
		if ret_val == 3:
			dnl = '\n\n'
			logging.error(f'Illegal instruction found @ CSR:PC = {csr:02X}:{pc:04X}H')
			tk.messagebox.showerror('!!! Illegal Instruction !!!', F'Illegal instruction found!\nCSR:PC = {csr:02X}:{pc:04X}H{dnl+"Single-step mode has been activated." if not single_step else ""}')
			set_single_step(True)
		if ret_val == 1: logging.warning(f'A write to a read-only region has happened @ CSR:PC = {csr:02X}:{pc:04X}H')
		if ret_val == 2: logging.warning(f'An unimplemented instruction has been skipped @ address {csr:01X}{(pc - 2) & 0xffff:04X}H')
		
		print_regs()

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

	screen_data = [[scr_bytes[1+i][j] & (1 << k) for j in range(0xb, -1, -1) for k in range(7, -1, -1)] for i in range(31)]

	for i in range(len(screen_data_status_bar)):
		if screen_data_status_bar[i]: screen.blit(status_bar, (58 + status_bar_crops[i][0], 132), status_bar_crops[i])

	for y in range(31):
		for x in range(96):
			if screen_data[y][x]: pygame.draw.rect(screen, (0, 0, 0), (58 + (x*3 - 96) % 288, 144 + y*3, 3, 3))

	if single_step: step = False

	pygame.display.update()
	root.update()
	root.after(0, pygame_loop)

simu8.coreReset()
print_regs()
pygame_loop()

style = ttk.Style()
style.configure('Con.TButton', background = console_bg)

step_bt = ttk.Button(root, text = 'Step', style = 'Con.TButton', command = set_step)
step_bt.place(rely = 1.0, relx = 1.0, x = 0, y = 0, anchor = 'se')
step_bt.focus_set()

root.mainloop()
