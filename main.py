import os
import sys
import time
import ctypes
import pygame
import logging
import functools
import threading
import traceback
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox

import config

logging.basicConfig(datefmt = config.dt_format, format = '[%(asctime)s] %(levelname)s: %(message)s')

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

def validate_hex(max_chars, new_char, new_str, act_code, rang = None):
	max_chars, act_code = int(max_chars), int(act_code)
	if rang: rang = eval(rang)

	if len(new_str) > max_chars: return False

	if act_code == 1:
		try: new_value_int = int(new_char, 16)
		except ValueError: return False
		if rang and len(new_str) == max_chars and int(new_str, 16) not in rang: return False
		else: return True
	else: return True

def get_var(var, typ): return typ.in_dll(simu8, var)

def read_dmem(addr, num_bytes, segment = 0):
	odd = addr % 2 != 0
	if odd:
		addr -= 1
		num_bytes += 1

	data = b''
	bytes_grabbed = 0

	while bytes_grabbed < num_bytes:
		remaining = num_bytes - bytes_grabbed
		if remaining >= 8: grab = 8
		elif remaining >= 4: grab = 4
		elif remaining >= 2: grab = 2
		else: grab = 1

		simu8.memoryGetData(ctypes.c_uint8(segment), ctypes.c_uint16(addr + bytes_grabbed), ctypes.c_size_t(grab))
		dt = get_var('DataRaw', Data_t)
		if grab == 8: dt_ = dt.qword
		elif grab == 4: dt_ = dt.dword
		elif grab == 2: dt_ = dt.word
		else: dt_ = dt.byte
		data += dt_.to_bytes(grab, 'little')
		bytes_grabbed += grab

	if odd: return data[1:]
	else: return data

def read_cmem(addr, segment = 0):
	simu8.memoryGetCodeWord(ctypes.c_uint8(segment), ctypes.c_uint16(addr))
	return get_var('CodeWord', ctypes.c_uint16).value

def calc_checksum():
	csum = 0
	csum1 = int.from_bytes(read_dmem(0xfffc, 2, 1), 'little')
	for i in range(0x10000): csum -= int.from_bytes(read_dmem(i, 1, 8), 'big')
	for i in range(0xfffc): csum -= int.from_bytes(read_dmem(i, 1, 1), 'big')
	csum %= 0x10000
	tk.messagebox.showinfo('Checksum', f'Expected checksum: {csum1:04X}\nCalculated checksum: {csum:04X}\n\n{"This looks like a good dump!" if csum == csum1 else "This is either a bad dump or an emulator ROM."}')

def set_csr_pc():
	get_var('CSR', ctypes.c_uint8).value = int(jump_csr_entry.get(), 16)
	get_var('PC', ctypes.c_uint16).value = int(jump_pc_entry.get(), 16)
	print_regs()
	w_jump.withdraw()

	jump_csr_entry.delete(0, 'end'); jump_csr_entry.insert(0, '0')
	jump_pc_entry.delete(0, 'end')

data_cache = {}
def init_mem():
	global data_cache

	seg = int(segment_var.get().split()[1])

	code_text['state'] = 'normal'
	code_text.delete('1.0', 'end')
	for i in range(0, 0x10000, 16):
		string = f'{seg:X}:{i:04X}  ' + ('?? '*16) + '  ' + '?'*16
		data_cache[i // 16] = string
		code_text.insert('end', string + '\n')
	code_text.delete('end-1c', 'end')
	code_text['state'] = 'disabled'

def open_mem():
	get_mem()
	w_data_mem.deiconify()

def sb_yview(*args):
	code_text.yview(*args)
	get_mem()

line_count = 50
def get_mem():
	if not ok: return

	global data_cache

	seg = int(segment_var.get().split()[1])

	code_text['state'] = 'normal'
	yview = code_text.yview()

	if single_step:
		data_str = format_mem(seg, read_dmem(0, 0x10000, seg), 0)
		data_cache = data_str
		code_text.delete('1.0', 'end')
		code_text.insert('end', '\n'.join(data_str.values()) + '\n')
	else:
		sl = int(yview[0] * 4096)
		addr = sl * 16
		if addr + line_count*16 > 0x10000: lines = 4096 - sl
		else: lines = line_count

		data_str = format_mem(seg, read_dmem(addr, lines*16, seg), addr)
		for k, v in data_str.items():
			if data_cache[k] != v:
				code_text.delete(f'{k+1}.0', f'{k+2}.0')
				if code_text.get('end-2c', 'end-1c') != '\n': code_text.insert('end', '\n')
				code_text.insert(f'{k+1}.0', v + '\n')
				data_cache[k] = v
	code_text.delete('end-1c', 'end')

	code_text.yview_moveto(yview[0])
	code_text['state'] = 'disabled'

	root.update_idletasks()

@functools.lru_cache
def format_mem(seg, data, addr):
	lines = {}
	j = addr // 16
	for i in range(addr, addr + len(data), 16):
		line = ''
		line_ascii = ''
		for byte in data[i-addr:i-addr+16]: line += f'{byte:02X} '; line_ascii += chr(byte) if byte in range(0x20, 0x7f) else '.'
		lines[j] = f'{seg:X}:{i % 0x10000:04X}  {line}  {line_ascii}'
		j += 1
	return lines

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
	global single_step

	if single_step == val: return

	single_step = val
	if val:
		print_regs()
		get_mem()
	else: threading.Thread(target = core_step_loop, daemon = True).start()

def open_popup(x):
	try: rc_menu.tk_popup(x.x_root, x.y_root)
	finally: rc_menu.grab_release()

def core_step():
	global ok

	ok = False
	ret_val = simu8.coreStep()
	ok = True
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

def core_step_loop():
	while not single_step: core_step()

def print_regs():
	gr = get_var('GR', GR_t)
	csr = get_var('CSR', ctypes.c_uint8).value
	pc = get_var('PC', ctypes.c_uint16).value
	sp = get_var('SP', ctypes.c_uint16).value
	psw = get_var('PSW', PSW_t).field
	info_label['text'] = f'''\
=== REGISTERS ===

General registers:
R0   R1   R2   R3   R4   R5   R6   R7
''' + '   '.join(f'{(gr.qrs[0] >> (i*8)) & 0xff:02X}' for i in range(8)) + f'''
 
R8   R9   R10  R11  R12  R13  R14  R15
''' + '   '.join(f'{(gr.qrs[1] >> (i*8)) & 0xff:02X}' for i in range(8)) + f'''

Control registers:
CSR:PC          {csr:02X}:{pc:04X}H
Words @ CSR:PC  {read_cmem(pc, csr):04X} {read_cmem(pc + 2, csr):04X} {read_cmem(pc + 4, csr):04X}
SP              {sp:04X}H
Words @ SP      ''' + ' '.join(format(int.from_bytes(read_dmem(sp + i, 2), 'little'), '04X') for i in range(0, 8, 2)) + f'''
                ''' + ' '.join(format(int.from_bytes(read_dmem(sp + i, 2), 'little'), '04X') for i in range(8, 16, 2)) + f'''
DSR:EA          {get_var('DSR', ctypes.c_uint8).value:01X}:{get_var('EA', ctypes.c_uint16).value:04X}H

                C Z S OV MIE HC ELEVEL
PSW             {psw.C} {psw.Z} {psw.S}  {psw.OV}  {psw.MIE}   {psw.HC} {psw.ELevel:02b} ({psw.ELevel})

LCSR:LR         {get_var('LCSR', ctypes.c_uint8).value:02X}:{get_var('LR', ctypes.c_uint16).value:04X}H
ECSR1:ELR1      {get_var('ECSR1', ctypes.c_uint8).value:02X}:{get_var('ELR1', ctypes.c_uint16).value:04X}H
ECSR2:ELR2      {get_var('ECSR2', ctypes.c_uint8).value:02X}:{get_var('ELR2', ctypes.c_uint16).value:04X}H
ECSR3:ELR3      {get_var('ECSR3', ctypes.c_uint8).value:02X}:{get_var('ELR3', ctypes.c_uint16).value:04X}H

EPSW1           {get_var('EPSW1', PSW_t).raw:02X}
EPSW2           {get_var('EPSW2', PSW_t).raw:02X}
EPSW3           {get_var('EPSW3', PSW_t).raw:02X}

{'Breakpoint set to ' + format(brkpoint >> 16, '02X') + ':' + format(brkpoint % 0x10000, '04X') + 'H' if brkpoint is not None else 'No breakpoint set.'}
''' if single_step or (not single_step and show_regs.get()) else '=== REGISTER DISPLAY DISABLED ===\nTo enable, do one of these things:\n- Enable single-step.\n- Press R or right-click >\n  Show registers outside of single-step.'

def draw_text(text, size, x, y, color = (255, 255, 255), font_name = None, anchor = 'center'):
	font = pygame.font.SysFont(font_name, int(size))
	text_surface = font.render(str(text), True, color)
	text_rect = text_surface.get_rect()
	exec('text_rect.' + anchor + ' = (x,y)')
	screen.blit(text_surface, text_rect)

@functools.lru_cache
def get_scr_data(*scr_bytes):
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

	return screen_data_status_bar, screen_data

def reset_core():
	simu8.coreReset()
	print_regs()
	get_mem()

def exit_sim():
	simu8.coreReset()
	simu8.memoryFree()
	pygame.display.quit()
	pygame.quit()
	root.quit()
	if os.name != 'nt': os.system('xset r on')
	sys.exit()

import platform
if sys.version_info < (3, 6, 0, 'alpha', 4):
	print(f'This program requires at least Python 3.6.0a4. (You are running Python {platform.python_version()})')
	sys.exit()

if pygame.version.vernum < (2, 2, 0):
	print(f'This program requires at least Pygame 2.2.0. (You are running Pygame {pygame.version.ver})')
	sys.exit()

simu8 = ctypes.CDLL(os.path.abspath(config.shared_lib))

root = tk.Tk()
root.geometry(f'{config.width*2}x{config.height}')
root.resizable(False, False)
root.title(config.root_w_name)
root.focus_set()
root['bg'] = config.console_bg

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
w_data_mem.geometry(f'{config.data_mem_width}x{config.data_mem_height}')
w_data_mem.resizable(False, False)
w_data_mem.title('Show data memory')
w_data_mem.protocol('WM_DELETE_WINDOW', w_data_mem.withdraw)

segment_var = tk.StringVar(); segment_var.set('Segment 0')
segment_cb = ttk.Combobox(w_data_mem, textvariable = segment_var, values = [f'Segment {i}' for i in range(16)])
segment_cb.bind('<<ComboboxSelected>>', lambda x: get_mem())
segment_cb.pack()

code_frame = ttk.Frame(w_data_mem)
code_text_sb = tk.Scrollbar(code_frame)
code_text_sb.pack(side = 'right', fill = 'y')
code_text = tk.Text(code_frame, font = config.data_mem_font, yscrollcommand = code_text_sb.set, wrap = 'none', state = 'disabled')
code_text_sb.config(command = sb_yview)
code_text.pack(fill = 'both', expand = True)
code_frame.pack(fill = 'both', expand = True)

embed_pygame = tk.Frame(root, width = config.width, height = config.height)
embed_pygame.pack(side = 'left')

info_label = tk.Label(root, text = 'Loading...', width = config.width, height = config.height, font = config.console_font, fg = config.console_fg, bg = config.console_bg, justify = 'left', anchor = 'nw')
info_label.pack(side = 'left')

os.environ['SDL_WINDOWID'] = str(embed_pygame.winfo_id())
os.environ['SDL_VIDEODRIVER'] = 'windib' if os.name == 'nt' else 'x11'
pygame.init()
pygame.display.init()
screen = pygame.display.set_mode()

interface = pygame.image.load(config.interface_path)
interface_rect = interface.get_rect()
status_bar = pygame.image.load(config.status_bar_path)
status_bar_rect = status_bar.get_rect()

ret_val = simu8.memoryInit(ctypes.c_char_p(config.rom_file.encode()), None)
if ret_val == 2:
	logging.error('Unable to allocate RAM for emulated memory.')
	sys.exit(-1)
elif ret_val == 3:
	logging.error(f'Cannot open the ROM file {rom_file}. If the file exists, please check the settings in config.py.')
	sys.exit(-1)

show_regs = tk.BooleanVar(value = True)
disp_lcd = tk.BooleanVar(value = True)

rc_menu = tk.Menu(root, tearoff = 0)
rc_menu.add_command(label = 'Enable single-step mode', accelerator = 'S', command = lambda: set_single_step(True))
rc_menu.add_command(label = 'Resume execution', accelerator = 'P', command = lambda: set_single_step(False))
rc_menu.add_separator()
rc_menu.add_command(label = 'Jump to...', accelerator = 'J', command = w_jump.deiconify)
rc_menu.add_separator()
rc_menu.add_command(label = 'Set breakpoint to...', accelerator = 'B', command = w_brkpoint.deiconify)
rc_menu.add_command(label = 'Clear breakpoint', accelerator = 'N', command = clear_brkpoint)
rc_menu.add_separator()
rc_menu.add_command(label = 'Show data memory', accelerator = 'M', command = open_mem)
rc_menu.add_separator()
rc_menu.add_checkbutton(label = 'Show registers outside of single-step', accelerator = 'R', variable = show_regs)
rc_menu.add_checkbutton(label = 'Toggle LCD/buffer display (on: LCD, off: buffer)', accelerator = 'D', variable = disp_lcd)
rc_menu.add_separator()
rc_menu.add_command(label = 'Reset core', accelerator = 'C', command = reset_core)
rc_menu.add_separator()

extra_funcs = tk.Menu(rc_menu, tearoff = 0)
extra_funcs.add_command(label = 'Calculate checksum', command = calc_checksum)
rc_menu.add_cascade(label = 'Extra functions', menu = extra_funcs)

rc_menu.add_separator()
rc_menu.add_command(label = 'Quit', accelerator = 'Q', command = exit_sim)

root.bind('<Button-3>', open_popup)
root.bind('s', lambda x: set_single_step(True)); root.bind('S', lambda x: set_single_step(True))
root.bind('p', lambda x: set_single_step(False)); root.bind('P', lambda x: set_single_step(False))
root.bind('j', lambda x: w_jump.deiconify()); root.bind('J', lambda x: w_jump.deiconify())
root.bind('b', lambda x: w_brkpoint.deiconify()); root.bind('B', lambda x: w_brkpoint.deiconify())
root.bind('n', lambda x: clear_brkpoint()); root.bind('N', lambda x: clear_brkpoint())
root.bind('m', lambda x: open_mem()); root.bind('M', lambda x: open_mem())
root.bind('r', lambda x: show_regs.set(not show_regs.get())); root.bind('R', lambda x: show_regs.set(not show_regs.get()))
root.bind('d', lambda x: disp_lcd.set(not disp_lcd.get())); root.bind('D', lambda x: disp_lcd.set(not disp_lcd.get()))
root.bind('c', lambda x: reset_core()); root.bind('C', lambda x: reset_core())
root.bind('q', lambda x: exit_sim()); root.bind('Q', lambda x: exit_sim())

single_step = ok = True
step, brkpoint = False, None
clock = pygame.time.Clock()

def pygame_loop():
	global single_step, step, brkpoint

	screen.fill((0, 0, 0))

	for event in pygame.event.get():
		if event.type == pygame.QUIT: exit_sim()

	if single_step and step: core_step()
	if (single_step and step) or not single_step:
		print_regs()
		if w_data_mem.winfo_viewable(): get_mem()

	clock.tick()

	screen.fill((0, 0, 0))
	screen.blit(interface, interface_rect)
	
	draw_text(f'Displaying {"LCD" if disp_lcd.get() else "buffer"}', 22, config.width // 2, 22, config.pygame_color, anchor = 'midtop')
	scr_bytes = [read_dmem((0xf000 if disp_lcd.get() else 0x87d0) + i*0x10, 0xc) for i in range(0x80, 0xa0)]
	screen_data_status_bar, screen_data = get_scr_data(*scr_bytes)

	for i in range(len(screen_data_status_bar)):
		if screen_data_status_bar[i]: screen.blit(status_bar, (58 + config.status_bar_crops[i][0], 132), config.status_bar_crops[i])

	for y in range(31):
		for x in range(96):
			if screen_data[y][x]: pygame.draw.rect(screen, (0, 0, 0), (58 + x*3, 144 + y*3, 3, 3))

	if single_step: step = False
	else: draw_text(f'{clock.get_fps():.1f} FPS', 22, config.width // 2, 44, config.pygame_color, anchor = 'midtop')

	pygame.display.update()
	root.update()
	root.after(0, pygame_loop)

reset_core()
pygame_loop()

root.bind('<KeyPress>', lambda x: set_step())

if os.name != 'nt': os.system('xset r off')
root.mainloop()
