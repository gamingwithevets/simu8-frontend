import os
import sys
import math
import time
import ctypes
import pygame
import struct
import logging
import functools
import threading
import traceback
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font
import tkinter.messagebox
from enum import IntEnum

from pyu8disas import main as disas
import platform

if sys.version_info < (3, 6, 0, 'alpha', 4):
	print(f'This program requires at least Python 3.6.0a4. (You are running Python {platform.python_version()})')
	sys.exit()

if pygame.version.vernum < (2, 2, 0):
	print(f'This program requires at least Pygame 2.2.0. (You are running Pygame {pygame.version.ver})')
	sys.exit()

exec(f'import {sys.argv[1]+" as " if len(sys.argv) > 1 else ""}config')
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

# https://github.com/JamesGKent/python-tkwidgets/blob/master/Debounce.py
class Debounce():
	'''
	When holding a key down, multiple key press and key release events are fired in
	succession. Debouncing is implemented in order to squash these repeated events
	and know when the "real" KeyRelease and KeyPress events happen.
	Use by subclassing a tkinter widget along with this class:
		class DebounceTk(Debounce, tk.Tk):
			pass
	'''
	
	# use classname as key to store class bindings
	# as single dict for all instances
	_bind_class_dict = {}
	
	# 'all' bindings stored here
	# single dict for all instances
	_bind_all_dict = {}
	
	def bind(self, event, function, debounce=True):
		'''
		Override the bind method, acts as normal binding if not KeyPress or KeyRelease
		type events, optional debounce parameter can be set to false to force normal behavior
		'''
		self._debounce_init()
		self._debounce_bind(event, function, debounce,
			self._binding_dict, self._base.bind)
			
	def bind_all(self, event, function, debounce=True):
		'''
		Override the bind_all method, acts as normal binding if not KeyPress or KeyRelease
		type events, optional debounce parameter can be set to false to force normal behavior
		'''
		self._debounce_init()
		self._debounce_bind(event, function, debounce,
			self._bind_all_dict, self._base.bind_all)
		
	def bind_class(self, event, function, debounce=True):
		'''
		Override the bind_class method, acts as normal binding if not KeyPress or KeyRelease
		type events, optional debounce parameter can be set to false to force normal behavior
		unlike underlying tk bind_class this uses name of class on which its called
		instead of requireing clas name as a parameter
		'''
		self._debounce_init()
		self._debounce_bind(event, function, debounce,
			self._bind_class_dict[self.__class__.__name__],
			self._base.bind_class, self.__class__.__name__)
			
	def _debounce_bind(self, event, function, debounce, bind_dict, bind_method, *args):
		'''
		internal method to implement binding
		'''
		self._debounce_init()
		# remove special symbols and split at first hyphen if present
		ev = event.replace("<", "").replace(">", "").split('-', 1)
		# if debounce and a supported event
		if (('KeyPress' in ev) or ('KeyRelease' in ev)) and debounce:
			if len(ev) == 2: # not generic binding so use keynames as key
				evname = ev[1]
			else: # generic binding, use event type
				evname = ev[0]
			if evname in bind_dict: # if have prev binding use that dict
				d = bind_dict[evname]
			else: # no previous binding, create new default dict
				d = {'has_prev_key_release':None, 'has_prev_key_press':False}

			# add function to dict (as keypress or release depending on name)
			d[ev[0]] = function
			# save binding back into dict
			bind_dict[evname] = d
			# call base class binding
			if ev[0] == 'KeyPress':
				bind_method(self, *args, sequence=event, func=self._on_key_press_repeat)
			elif ev[0] == 'KeyRelease':
				bind_method(self, *args, sequence=event, func=self._on_key_release_repeat)
				
		else: # not supported or not debounce, bind as normal
			bind_method(self, *args, sequence=event, func=function)
			
	def _debounce_init(self):
		# get first base class that isn't Debounce and save ref
		# this will be used for underlying bind methods
		if not hasattr(self, '_base'):
			for base in self.__class__.__bases__:
				if base.__name__ != 'Debounce':
					self._base = base
					break
		# for instance bindings
		if not hasattr(self, '_binding_dict'):
			self._binding_dict = {}
			
		# for class bindings
		try: # check if this class has alread had class bindings
			cd = self._bind_class_dict[self.__class__.__name__]
		except KeyError: # create dict to store if not
			self._bind_class_dict[self.__class__.__name__] = {}
			
		# get the current bind tags
		bindtags = list(self.bindtags())
		# add our custom bind tag before the origional bind tag
		index = bindtags.index(self._base.__name__)
		bindtags.insert(index, self.__class__.__name__)
		# save the bind tags back to the widget
		self.bindtags(tuple(bindtags))
			
	def _get_evdict(self, event):
		'''
		internal method used to get the dictionaries that store the special binding info
		'''
		dicts = []
		names = {'2':'KeyPress', '3':'KeyRelease'}
		# loop through all applicable bindings
		for d in [self._binding_dict, # instance binding
			self._bind_class_dict[self.__class__.__name__], # class
			self._bind_all_dict]: # all
			evdict = None
			generic = False
			if event.type in names: # if supported event
				evname = event.keysym
				if evname not in d: # if no specific binding
					generic = True
					evname = names[event.type]
				try:
					evdict = d[evname]
				except KeyError:
					pass
			if evdict: # found a binding
				dicts.append((d, evdict, generic))
		return dicts
		
	def _on_key_release(self, event):
		'''
		internal method, called by _on_key_release_repeat only when key is actually released
		this then calls the method that was passed in to the bind method
		'''
		# get all binding details
		for d, evdict, generic in self._get_evdict(event):
			# call callback
			res = evdict['KeyRelease'](event)
			evdict['has_prev_key_release'] = None
			
			# record that key was released
			if generic:
				d['KeyPress'][event.keysym] = False
			else:
				evdict['has_prev_key_press'] = False
			# if supposed to break propagate this up
			if res == 'break':
				return 'break'
		
	def _on_key_release_repeat(self, event):
		'''
		internal method, called by the 'KeyRelease' event, used to filter false events
		'''
		# get all binding details
		for d, evdict, generic in self._get_evdict(event):
			if evdict["has_prev_key_release"]:
				# got a previous release so cancel it
				self.after_cancel(evdict["has_prev_key_release"])
				evdict["has_prev_key_release"] = None
			# queue new event for key release
			evdict["has_prev_key_release"] = self.after_idle(self._on_key_release, event)
		
	def _on_key_press(self, event):
		'''
		internal method, called by _on_key_press_repeat only when key is actually pressed
		this then calls the method that was passed in to the bind method
		'''
		# get all binding details
		for d, evdict, generic in self._get_evdict(event):
			# call callback
			res = evdict['KeyPress'](event)
			# record that key was pressed
			if generic:
				evdict[event.keysym] = True
			else:
				evdict['has_prev_key_press'] = True
			# if supposed to break propagate this up
			if res == 'break':
				return 'break'
		
	def _on_key_press_repeat(self, event):
		'''
		internal method, called by the 'KeyPress' event, used to filter false events
		'''
		# get binding details
		for d, evdict, generic in self._get_evdict(event):
			if not generic:
				if evdict["has_prev_key_release"]:
					# got a previous release so cancel it
					self.after_cancel(evdict["has_prev_key_release"])
					evdict["has_prev_key_release"] = None
				else:
					# if not pressed before (real event)
					if evdict['has_prev_key_press'] == False:
						self._on_key_press(event)
			else:
				# if not pressed before (real event)
				if (event.keysym not in evdict) or (evdict[event.keysym] == False):
					self._on_key_press(event)

class DebounceTk(Debounce, tk.Tk): pass

class Jump(tk.Toplevel):
	def __init__(self, sim):
		super(Jump, self).__init__()
		self.sim = sim

		self.withdraw()
		self.geometry('250x100')
		self.resizable(False, False)
		self.title('Jump to address')
		self.protocol('WM_DELETE_WINDOW', self.withdraw)
		self.vh_reg = self.register(self.sim.validate_hex)
		ttk.Label(self, text = 'Input new values for CSR and PC.\n(please input hex bytes)', justify = 'center').pack()
		self.csr = tk.Frame(self); self.csr.pack(fill = 'x')
		ttk.Label(self.csr, text = 'CSR').pack(side = 'left')
		self.csr_entry = ttk.Entry(self.csr, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', range(0x10))); self.csr_entry.pack(side = 'right')
		self.csr_entry.insert(0, '0')
		self.pc = tk.Frame(self); self.pc.pack(fill = 'x')
		ttk.Label(self.pc, text = 'PC').pack(side = 'left')
		self.pc_entry = ttk.Entry(self.pc, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', range(0, 0xfffe, 2))); self.pc_entry.pack(side = 'right')
		ttk.Button(self, text = 'OK', command = self.set_csr_pc).pack(side = 'bottom')
		self.bind('<Return>', lambda x: self.set_csr_pc())
		self.bind('<Escape>', lambda x: self.withdraw())

	def set_csr_pc(self):
		csr_entry = self.csr_entry.get()
		pc_entry = self.pc_entry.get()
		self.sim.get_var('CSR', ctypes.c_uint8).value = int(csr_entry, 16) if csr_entry else 0
		self.sim.get_var('PC', ctypes.c_uint16).value = int(pc_entry, 16) if pc_entry else 0
		self.sim.print_regs()
		self.withdraw()

		self.csr_entry.delete(0, 'end'); self.csr_entry.insert(0, '0')
		self.pc_entry.delete(0, 'end')

class Brkpoint(tk.Toplevel):
	def __init__(self, sim):
		super(Brkpoint, self).__init__()
		self.sim = sim

		self.withdraw()
		self.geometry('300x125')
		self.resizable(False, False)
		self.title('Set breakpoint')
		self.protocol('WM_DELETE_WINDOW', self.withdraw)
		self.vh_reg = self.register(self.sim.validate_hex)
		ttk.Label(self, text = 'Single-step mode will be activated if CSR:PC matches\nthe below. Note that only 1 breakpoint can be set.\n(please input hex bytes)', justify = 'center').pack()
		self.csr = tk.Frame(self); self.csr.pack(fill = 'x')
		ttk.Label(self.csr, text = 'CSR').pack(side = 'left')
		self.csr_entry = ttk.Entry(self.csr, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', range(0x10))); self.csr_entry.pack(side = 'right')
		self.csr_entry.insert(0, '0')
		self.pc = tk.Frame(self); self.pc.pack(fill = 'x')
		ttk.Label(self.pc, text = 'PC').pack(side = 'left')
		self.pc_entry = ttk.Entry(self.pc, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', range(0, 0xfffe, 2))); self.pc_entry.pack(side = 'right')
		ttk.Button(self, text = 'OK', command = self.set_brkpoint).pack(side = 'bottom')
		self.bind('<Return>', lambda x: self.set_brkpoint())
		self.bind('<Escape>', lambda x: self.withdraw())

	def set_brkpoint(self):
		csr_entry = self.csr_entry.get()
		pc_entry = self.pc_entry.get()
		self.sim.breakpoint = ((int(csr_entry, 16) if csr_entry else 0) << 16) + (int(pc_entry, 16) if pc_entry else 0)
		self.sim.print_regs()
		self.withdraw()

		self.csr_entry.delete(0, 'end'); self.csr_entry.insert(0, '0')
		self.pc_entry.delete(0, 'end')

	def clear_brkpoint(self):
		self.sim.breakpoint = None
		self.sim.print_regs()

class Write(tk.Toplevel):
	def __init__(self, sim):
		super(Write, self).__init__()
		self.sim = sim
		
		tk_font = tk.font.nametofont('TkDefaultFont')
		bold_italic_font = tk_font.copy()
		bold_italic_font.config(weight = 'bold', slant = 'italic')

		self.withdraw()
		self.geometry('375x125')
		self.resizable(False, False)
		self.title('Write to data memory')
		self.protocol('WM_DELETE_WINDOW', self.withdraw)
		self.vh_reg = self.register(self.sim.validate_hex)
		ttk.Label(self, text = '(please input hex bytes)', justify = 'center').pack()
		self.csr = tk.Frame(self); self.csr.pack(fill = 'x')
		ttk.Label(self.csr, text = 'Segment').pack(side = 'left')
		self.csr_entry = ttk.Entry(self.csr, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', range(0x100))); self.csr_entry.pack(side = 'right')
		self.csr_entry.insert(0, '0')
		self.pc = tk.Frame(self); self.pc.pack(fill = 'x')
		ttk.Label(self.pc, text = 'Address').pack(side = 'left')
		self.pc_entry = ttk.Entry(self.pc, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', range(0x10000))); self.pc_entry.pack(side = 'right')
		self.byte = tk.Frame(self); self.byte.pack(fill = 'x')
		ttk.Label(self.byte, text = 'Hex data').pack(side = 'left')
		self.byte_entry = ttk.Entry(self.byte, validate = 'key', validatecommand = (self.vh_reg, '%S', '%P', '%d', None, 1)); self.byte_entry.pack(side = 'right')
		ttk.Button(self, text = 'OK', command = self.write).pack(side = 'bottom')
		self.bind('<Return>', lambda x: self.write())
		self.bind('<Escape>', lambda x: self.withdraw())

	def write(self):
		seg = self.csr_entry.get(); seg = int(seg, 16) if seg else 0
		adr = self.pc_entry.get(); adr = int(adr, 16) if adr else 0
		byte = self.byte_entry.get()
		try: byte = bytes.fromhex(byte) if byte else '\x00'
		except Exception: 
			tk.messagebox.showerror('Error', 'Invalid hex string!')
			return
		
		index = 0
		while index < len(byte):
			remaining = len(byte) - index
			if remaining > 8: num = 8
			else: num = remaining
			self.sim.write_dmem(adr + index, num, int.from_bytes(byte[index:index+num], 'little'), seg)
			index += num

		self.sim.print_regs()
		self.sim.data_mem.get_mem()
		self.withdraw()

		self.csr_entry.delete(0, 'end'); self.csr_entry.insert(0, '0')
		self.pc_entry.delete(0, 'end')
		self.byte_entry.delete(0, 'end'); self.byte_entry.insert(0, '0')

class DataMem(tk.Toplevel):
	def __init__(self, sim):
		super(DataMem, self).__init__()
		self.sim = sim

		self.withdraw()
		self.geometry(f'{config.data_mem_width}x{config.data_mem_height}')
		self.resizable(False, False)
		self.title('Show data memory')
		self.protocol('WM_DELETE_WINDOW', self.withdraw)

		self.segment_var = tk.StringVar(); self.segment_var.set('RAM (00:8000H - 00:EFFFH)')
		self.segment_cb = ttk.Combobox(self, width = 30, textvariable = self.segment_var, values = ['RAM (00:8000H - 00:EFFFH)', 'SFRs (00:F000H - 00:FFFFH)'])
		self.segment_cb.bind('<<ComboboxSelected>>', lambda x: self.get_mem(False))
		self.segment_cb.pack()

		self.code_frame = ttk.Frame(self)
		self.code_text_sb = ttk.Scrollbar(self.code_frame)
		self.code_text_sb.pack(side = 'right', fill = 'y')
		self.code_text = tk.Text(self.code_frame, font = config.data_mem_font, yscrollcommand = self.code_text_sb.set, wrap = 'none', state = 'disabled')
		self.code_text_sb.config(command = self.sb_yview)
		self.code_text.pack(fill = 'both', expand = True)
		self.code_frame.pack(fill = 'both', expand = True)

	def sb_yview(self, *args):
		self.code_text.yview(*args)
		self.get_mem()

	def open(self):
		self.get_mem()
		self.deiconify()

	def get_mem(self, keep_yview = True):
		rang = (0, 0x7000) if self.segment_var.get().split()[0] == 'RAM' else (0x7000, 0x1000)

		self.code_text['state'] = 'normal'
		yview_bak = self.code_text.yview()[0]
		self.code_text.delete('1.0', 'end')
		self.code_text.insert('end', self.format_mem(bytes((ctypes.c_byte*rang[1]).from_address(self.sim.get_var('DataMemory', ctypes.c_void_p).value + rang[0])), 0x8000 + rang[0]))
		if keep_yview: self.code_text.yview_moveto(str(yview_bak))
		self.code_text['state'] = 'disabled'

	@staticmethod
	@functools.lru_cache
	def format_mem(data, addr):
		lines = {}
		j = addr // 16
		for i in range(addr, addr + len(data), 16):
			line = ''
			line_ascii = ''
			for byte in data[i-addr:i-addr+16]: line += f'{byte:02X} '; line_ascii += chr(byte) if byte in range(0x20, 0x7f) else '.'
			lines[j] = f'00:{i % 0x10000:04X}  {line}  {line_ascii}'
			j += 1
		return '\n'.join(lines.values())

class Sim:
	def __init__(self):
		self.root = DebounceTk()
		self.root.geometry(f'{config.width*2}x{config.height}')
		self.root.resizable(False, False)
		self.root.title(config.root_w_name)
		self.root.focus_set()
		self.root['bg'] = config.console_bg

		self.sim = ctypes.CDLL(os.path.abspath(config.shared_lib))
		self.sim.memoryGetData.restype = ctypes.c_uint64
		self.sim.memoryInit(ctypes.c_char_p(config.rom_file.encode()), None)

		self.keys_pressed = set()
		self.keys = []
		for key in [i[1:] for i in config.keymap.values()]: self.keys.extend(key)

		self.jump = Jump(self)
		self.brkpoint = Brkpoint(self)
		self.write = Write(self)
		self.data_mem = DataMem(self)

		embed_pygame = tk.Frame(self.root, width = config.width, height = config.height)
		embed_pygame.pack(side = 'left')
		embed_pygame.focus_set()

		def press_cb(event):
			for k, v in config.keymap.items():
				p = v[0]
				if (event.type == tk.EventType.ButtonPress and event.x in range(p[0], p[0]+p[2]) and event.y in range(p[1], p[1]+p[3])) \
				or (event.type == tk.EventType.KeyPress and event.keysym.lower() in v[1:]):
					if k is None: self.reset_core(False)
					elif config.real_hardware: self.keys_pressed.add(k)
					else:
						self.write_dmem(0x8e01, 1, 1 << k[0])
						self.write_dmem(0x8e02, 1, 1 << k[1])

		def release_cb(event):
			if config.real_hardware: self.keys_pressed.clear()
			else:
				self.write_dmem(0x8e01, 1, 0)
				self.write_dmem(0x8e02, 1, 0)

		embed_pygame.bind('<KeyPress>', press_cb)
		embed_pygame.bind('<KeyRelease>', release_cb)
		embed_pygame.bind('<ButtonPress-1>', press_cb)
		embed_pygame.bind('<ButtonRelease-1>', release_cb)

		if os.name != 'nt': self.root.update()

		self.info_label = tk.Label(self.root, text = 'Loading...', width = config.width, height = config.height, font = config.console_font, fg = config.console_fg, bg = config.console_bg, justify = 'left', anchor = 'nw')
		self.info_label.pack(side = 'left')

		os.environ['SDL_WINDOWID'] = str(embed_pygame.winfo_id())
		os.environ['SDL_VIDEODRIVER'] = 'windib' if os.name == 'nt' else 'x11'
		pygame.init()
		self.screen = pygame.display.set_mode()

		self.interface = pygame.image.load(config.interface_path)
		self.interface_rect = self.interface.get_rect()
		self.status_bar = pygame.image.load(config.status_bar_path)
		self.status_bar_rect = self.status_bar.get_rect()

		self.show_regs = tk.BooleanVar(value = True)
		self.disp_lcd = tk.BooleanVar(value = True)

		self.rc_menu = tk.Menu(self.root, tearoff = 0)
		self.rc_menu.add_command(label = 'Step (single-step only)', accelerator = '\\', command = self.set_step)
		self.rc_menu.add_separator()
		self.rc_menu.add_command(label = 'Enable single-step mode', accelerator = 'S', command = lambda: self.set_single_step(True))
		self.rc_menu.add_command(label = 'Resume execution (unpause)', accelerator = 'P', command = lambda: self.set_single_step(False))
		self.rc_menu.add_separator()
		self.rc_menu.add_command(label = 'Jump to...', accelerator = 'J', command = self.jump.deiconify)
		self.rc_menu.add_separator()
		self.rc_menu.add_command(label = 'Set breakpoint to...', accelerator = 'B', command = self.brkpoint.deiconify)
		self.rc_menu.add_command(label = 'Clear breakpoint', accelerator = 'N', command = self.brkpoint.clear_brkpoint)
		self.rc_menu.add_separator()
		self.rc_menu.add_command(label = 'Show data memory', accelerator = 'M', command = self.data_mem.open)
		self.rc_menu.add_separator()
		self.rc_menu.add_checkbutton(label = 'Show registers outside of single-step', accelerator = 'R', variable = self.show_regs)
		self.rc_menu.add_checkbutton(label = 'Toggle LCD/buffer display (on: LCD, off: buffer)', accelerator = 'D', variable = self.disp_lcd)
		self.rc_menu.add_separator()
		self.rc_menu.add_command(label = 'Reset core', accelerator = 'C', command = self.reset_core)
		self.rc_menu.add_separator()

		extra_funcs = tk.Menu(self.rc_menu, tearoff = 0)
		extra_funcs.add_command(label = 'ROM info', command = self.calc_checksum)
		extra_funcs.add_command(label = 'Write to data memory', command = self.write.deiconify)
		self.rc_menu.add_cascade(label = 'Extra functions', menu = extra_funcs)
		self.rc_menu.add_separator()
		self.rc_menu.add_command(label = 'Quit', accelerator = 'Q', command = self.exit_sim)

		self.root.bind('<Button-3>', self.open_popup)
		self.root.bind('\\', lambda x: self.set_step())
		self.bind_('s', lambda x: self.set_single_step(True))
		self.bind_('p', lambda x: self.set_single_step(False))
		self.bind_('j', lambda x: self.jump.deiconify())
		self.bind_('b', lambda x: self.brkpoint.deiconify())
		self.bind_('n', lambda x: self.brkpoint.clear_brkpoint())
		self.bind_('m', lambda x: self.data_mem.open())
		self.bind_('r', lambda x: self.show_regs.set(not self.show_regs.get()))
		self.bind_('d', lambda x: self.disp_lcd.set(not self.disp_lcd.get()))
		self.bind_('c', lambda x: self.reset_core())
		self.bind_('q', lambda x: self.exit_sim())

		self.single_step = True
		self.ok = True
		self.step = False
		self.breakpoint = None
		self.clock = pygame.time.Clock()

		self.prev_csr_pc = None
		self.last_ready = 0
		self.stop_accept = [False, False]
		self.stop_mode = False

		self.ips = 0
		self.ips_start = time.time()
		self.ips_ctr = 0

	def run(self):
		self.reset_core()
		self.pygame_loop()

		if os.name != 'nt': os.system('xset r off')
		self.root.mainloop()

	def bind_(self, char, func):
		self.root.bind(char.lower(), func)
		self.root.bind(char.upper(), func)

	@staticmethod
	def validate_hex(new_char, new_str, act_code, rang = None, spaces = False):
		act_code = int(act_code)
		if rang: rang = eval(rang)
		
		if act_code == 1:
			try: new_value_int = int(new_char, 16)
			except ValueError:
				if new_char != ' ': return False
				elif not spaces: return False
			if rang and len(new_str) >= len(hex(rang[-1])[2:]) and int(new_str, 16) not in rang: return False

		return True

	def read_dmem(self, addr, num_bytes, segment = 0): return self.sim.memoryGetData(ctypes.c_uint8(segment), ctypes.c_uint16(addr), ctypes.c_size_t(num_bytes))

	def read_dmem_bytes(self, addr, num_bytes, segment = 0):
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

			dt = self.sim.memoryGetData(ctypes.c_uint8(segment), ctypes.c_uint16(addr + bytes_grabbed), ctypes.c_size_t(grab))
			data += dt.to_bytes(grab, 'little')
			bytes_grabbed += grab

		if odd: return data[1:]
		else: return data

	def write_dmem(self, addr, num_bytes, data, segment = 0):
		self.sim.memorySetData(ctypes.c_uint8(segment), ctypes.c_uint16(addr), ctypes.c_size_t(num_bytes), ctypes.c_uint64(data))

	def read_cmem(self, addr, segment = 0): return self.sim.memoryGetCodeWord(ctypes.c_uint8(segment), ctypes.c_uint16(addr))

	def calc_checksum(self):
		csum = 0
		version = self.read_dmem_bytes(0xfff4, 6, 1).decode()
		rev = self.read_dmem_bytes(0xfffa, 2, 1).decode()
		csum1 = self.read_dmem(0xfffc, 2, 1)
		for i in range(0x10000): csum -= self.read_dmem(i, 1, 8)
		for i in range(0xfffc): csum -= self.read_dmem(i, 1, 1)
		
		csum %= 0x10000
		text = f'{version} Ver{rev}\nSUM {csum:04X} {"OK" if csum == csum1 else "NG"}'
		
		tk.messagebox.showinfo('ROM info', text)

	def set_step(self): self.step = True

	def set_single_step(self, val):
		if self.single_step == val: return

		self.single_step = val
		if val:
			self.print_regs()
			self.data_mem.get_mem()
		else: threading.Thread(target = self.core_step_loop, daemon = True).start()

	def open_popup(self, x):
		try: self.rc_menu.tk_popup(x.x_root, x.y_root)
		finally: self.rc_menu.grab_release()

	def keyboard(self):
		if config.real_hardware:
			ki = 0xff
			ko = self.read_dmem(0xf046, 1)

			for ki_val, ko_val in self.keys_pressed:
				if ko & (1 << ko_val): ki &= ~(1 << ki_val)

			self.write_dmem(0xf040, 1, ki)
			if len(self.keys_pressed) > 0: self.write_dmem(0xf014, 1, 2)
		else:
			ready = self.read_dmem(0x8e00, 1)

			if not self.last_ready and ready:
				self.write_dmem(0x8e01, 1, 0)
				self.write_dmem(0x8e02, 1, 0)
			
			self.last_ready = ready

	def sbycon(self):
		sbycon = self.read_dmem(0xf009, 1)

		if sbycon == 2 and all(self.stop_accept):
			self.stop_mode = True
			self.write_dmem(0xf009, 1, 0)
			self.write_dmem(0xf008, 0, 0)
			self.stop_accept = [False, False]

	def timer(self):
		counter = self.read_dmem(0xf022, 2)
		target = self.read_dmem(0xf020, 2)

		counter += 1
		counter &= 0xffff

		self.write_dmem(0xf022, 2, counter)

		if counter >= target and self.stop_mode:
			self.stop_mode = False
			if config.real_hardware: self.write_dmem(0xf014, 1, 0x20)

	def get_var(self, var, typ): return typ.in_dll(self.sim, var)

	def core_step(self):
		self.prev_csr_pc = f"{self.get_var('CSR', ctypes.c_uint8).value:X}:{self.get_var('PC', ctypes.c_uint16).value:04X}H"

		self.keyboard()
		self.sbycon()
		self.timer()

		if not self.stop_mode:
			self.ok = False
			retval = None
			try: retval = self.sim.coreStep()
			except Exception as e: logging.error(str(e))

			csr = self.get_var('CSR', ctypes.c_uint8).value
			pc = self.get_var('PC', ctypes.c_uint16).value

			if retval == 2: logging.warning(f'unimplemented instruction @ {csr:X}:{(pc - 2) & 0xffff:04X}H')
			elif retval == 3: logging.error(f'illegal instruction @ {csr:X}:{pc:04X}H')

			stpacp = self.read_dmem(0xf008, 1)
			if self.stop_accept[0]:
				if stpacp & 0xa0 == 0xa0 and not self.stop_accept[1]: self.stop_accept[1] = True
			elif stpacp & 0x50 == 0x50: self.stop_accept[0] = True

			self.ok = True

			if self.ips_ctr % 1000 == 0:
				cur = time.time()
				try: self.ips = 1000 / (cur - self.ips_start)
				except ZeroDivisionError: self.ips = None
				self.ips_start = cur

			self.ips_ctr += 1

		csr = self.get_var('CSR', ctypes.c_uint8).value
		pc = self.get_var('PC', ctypes.c_uint16).value
		if (csr << 16) + pc == self.breakpoint:
			tk.messagebox.showinfo('Breakpoint hit!', f'Breakpoint {csr:X}:{pc:04X}H has been hit!')
			self.set_single_step(True)

	def core_step_loop(self):
		while not self.single_step: self.core_step()

	def print_regs(self):
		gr = self.get_var('GR', GR_t)
		csr = self.get_var('CSR', ctypes.c_uint8).value
		pc = self.get_var('PC', ctypes.c_uint16).value
		sp = self.get_var('SP', ctypes.c_uint16).value
		psw = self.get_var('PSW', PSW_t)
		psw_val = psw.raw
		psw_field = psw.field

		self.info_label['text'] = f'''\
=== REGISTERS ===

General registers:
R0   R1   R2   R3   R4   R5   R6   R7
''' + '   '.join(f'{(gr.qrs[0] >> (i*8)) & 0xff:02X}' for i in range(8)) + f'''
 
R8   R9   R10  R11  R12  R13  R14  R15
''' + '   '.join(f'{(gr.qrs[1] >> (i*8)) & 0xff:02X}' for i in range(8)) + f'''

Control registers:
CSR:PC          {csr:X}:{pc:04X}H (prev. value: {self.prev_csr_pc})
Words @ CSR:PC  ''' + ' '.join(format(self.read_cmem((pc + i*2) & 0xfffe, csr), '04X') for i in range(3)) + f'''
Instruction     {self.decode_instruction()}
SP              {sp:04X}H
Words @ SP      ''' + ' '.join(format(self.read_dmem(sp + i, 2), '04X') for i in range(0, 8, 2)) + f'''
                ''' + ' '.join(format(self.read_dmem(sp + i, 2), '04X') for i in range(8, 16, 2)) + f'''
DSR:EA          {self.get_var('DSR', ctypes.c_uint8).value:02X}:{self.get_var('EA', ctypes.c_uint16).value:04X}H

                   C Z S OV MIE HC ELEVEL
PSW             {psw_val:02X} {psw_field.C} {psw_field.Z} {psw_field.S}  {psw_field.OV}  {psw_field.MIE}   {psw_field.HC} {psw_field.ELevel:02b} ({psw_field.ELevel})

LCSR:LR         {self.get_var('LCSR', ctypes.c_uint8).value:X}:{self.get_var('LR', ctypes.c_uint16).value:04X}H
ECSR1:ELR1      {self.get_var('ECSR1', ctypes.c_uint8).value:X}:{self.get_var('ELR1', ctypes.c_uint16).value:04X}H
ECSR2:ELR2      {self.get_var('ECSR2', ctypes.c_uint8).value:X}:{self.get_var('ELR2', ctypes.c_uint16).value:04X}H
ECSR3:ELR3      {self.get_var('ECSR3', ctypes.c_uint8).value:X}:{self.get_var('ELR3', ctypes.c_uint16).value:04X}H

EPSW1           {self.get_var('EPSW1', PSW_t).raw:02X}
EPSW2           {self.get_var('EPSW2', PSW_t).raw:02X}
EPSW3           {self.get_var('EPSW3', PSW_t).raw:02X}

Other information:
Breakpoint               {format(self.breakpoint >> 16, 'X') + ':' + format(self.breakpoint % 0x10000, '04X') + 'H' if self.breakpoint is not None else 'None'}
STOP mode acceptor       Level 1 [{'x' if self.stop_accept[0] else ' '}]
                         Level 2 [{'x' if self.stop_accept[1] else ' '}]
STOP mode                [{'x' if self.stop_mode else ' '}]
Instructions per second  {format(self.ips, '.1f') if self.ips is not None and not self.single_step else 'None'}\
''' if self.single_step or (not self.single_step and self.show_regs.get()) else '=== REGISTER DISPLAY DISABLED ===\nTo enable, do one of these things:\n- Enable single-step.\n- Press R or right-click >\n  Show registers outside of single-step.'

	def decode_instruction(self):
		disas.input_file = b''
		for i in range(3): disas.input_file += self.read_cmem((self.get_var('PC', ctypes.c_uint16).value + i*2) & 0xfffe, self.get_var('CSR', ctypes.c_uint16).value).to_bytes(2, 'little')
		disas.addr = 0
		ins_str, _, dsr_prefix, _ = disas.decode_ins()
		if dsr_prefix: ins_str, _, _, _ = disas.decode_ins()
		return ins_str

	def draw_text(self, text, size, x, y, color = (255, 255, 255), font_name = None, anchor = 'center'):
		font = pygame.font.SysFont(font_name, int(size))
		text_surface = font.render(str(text), True, color)
		text_rect = text_surface.get_rect()
		exec('text_rect.' + anchor + ' = (x,y)')
		self.screen.blit(text_surface, text_rect)

	@staticmethod
	@functools.lru_cache
	def get_scr_data(*scr_bytes):
		sbar = scr_bytes[0]
		screen_data_status_bar = [
		sbar[0]   & (1 << 4),  # [S]
		sbar[0]   & (1 << 2),  # [A]
		sbar[1]   & (1 << 4),  # M
		sbar[1]   & (1 << 1),  # STO
		sbar[2]   & (1 << 6),  # RCL
		sbar[3]   & (1 << 6),  # STAT
		sbar[4]   & (1 << 7),  # CMPLX
		sbar[5]   & (1 << 6),  # MAT
		sbar[5]   & (1 << 1),  # VCT
		sbar[7]   & (1 << 5),  # [D]
		sbar[7]   & (1 << 1),  # [R]
		sbar[8]   & (1 << 4),  # [G]
		sbar[8]   & (1 << 0),  # FIX
		sbar[9]   & (1 << 5),  # SCI
		sbar[0xa] & (1 << 6),  # Math
		sbar[0xa] & (1 << 3),  # v
		sbar[0xb] & (1 << 7),  # ^
		sbar[0xb] & (1 << 4),  # Disp
		]

		screen_data = [[scr_bytes[1+i][j] & (1 << k) for j in range(0xc) for k in range(7, -1, -1)] for i in range(31)]

		return screen_data_status_bar, screen_data

	def reset_core(self, single_step = True):
		self.sim.coreReset()
		self.prev_csr_pc = None
		self.set_single_step(single_step)
		self.print_regs()
		self.data_mem.get_mem()

	def exit_sim(self):
		self.sim.memoryFree()
		pygame.quit()
		self.root.quit()
		if os.name != 'nt': os.system('xset r on')
		sys.exit()

	def pygame_loop(self):
		self.screen.fill((0, 0, 0))

		if self.single_step and self.step: self.core_step()
		if (self.single_step and self.step) or not self.single_step:
			self.print_regs()
			if self.data_mem.winfo_viewable(): self.data_mem.get_mem()

		self.clock.tick()

		self.screen.fill((0, 0, 0))
		self.screen.blit(self.interface, self.interface_rect)

		disp_lcd = self.disp_lcd.get()
		self.draw_text(f'Displaying {"LCD" if disp_lcd else "buffer"}', 22, config.width // 2, 22, config.pygame_color, anchor = 'midtop')

		scr_bytes = [self.read_dmem_bytes(0xf800 + i*0x10 if disp_lcd else 0x87d0 + i*0xc, 0xc) for i in range(0x20)]
		screen_data_status_bar, screen_data = self.get_scr_data(*scr_bytes)
		
		scr_range = self.read_dmem(0xf030, 1) & 7
		scr_mode = self.read_dmem(0xf031, 1) & 7

		if (disp_lcd and scr_mode in (5, 6)) or not disp_lcd:
			for i in range(len(screen_data_status_bar)):
				crop = config.status_bar_crops[i]
				if screen_data_status_bar[i]:
					self.screen.blit(self.status_bar, (config.screen_tl_w + crop[0], config.screen_tl_h), crop)
	
		if (disp_lcd and scr_mode == 5) or not disp_lcd:
			for y in range(scr_range if scr_range and disp_lcd else 31):
				for x in range(96):
					if screen_data[y][x]: pygame.draw.rect(self.screen, (0, 0, 0), (config.screen_tl_w + x*3, config.screen_tl_h + 12 + y*3, 3, 3))

		if self.single_step: self.step = False
		else: self.draw_text(f'{self.clock.get_fps():.1f} FPS', 22, config.width // 2, 44, config.pygame_color, anchor = 'midtop')

		pygame.display.update()
		self.root.update()
		self.root.after(0, self.pygame_loop)

if __name__ == '__main__':
	sim = Sim()
	sim.run()
