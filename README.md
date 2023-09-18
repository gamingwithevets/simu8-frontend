This is a **frontend** for [LifeEmu](https://github.com/LifeEmu)'s [SimU8](https://github.com/LifeEmu/SimU8) emulator written in Python. 
It's a very simple Tkinter window with Pygame embedded into it.

Currently, SimU8 is unfinished, therefore the frontend may look like it isn't working properly.
However, the screen **has been tested and verified to be working** via direct memory editing and jumping to various functions in the fx-570ES PLUS real ROM.

This frontend serves as a replacement to `testcore.c`, a console-only C script that's used for testing.
However, since this frontend is written in Python, it may be slow depending on your computer speed.

# Installation
Because SimU8 was written in C and this frontend was written in Python, a **shared library** is needed to use the frontend.
That's not really a big deal, however I thought I should mention it, as C compilers are usually used for compiling binaries and not shared libraries.

1. Clone this repository and the SimU8 submodule:
```
git clone https://github.com/gamingwithevets/simu8-frontend.git
git submodule update
```
2. Go to the repo directory and run the command below (this assumes the SimU8 submodule is located in the `SimU8` directory):
```
gcc SimU8/src/core.c SimU8/src/mmu.c -O3 -fPIC -shared -o simu8.so
```
3. Edit the `config.py` file as needed.
4. Run `python main.py` (or `python3 main.py`) and you're done.

# Usage
When you open the emulator, you can right-click to see the available functions of the emulator. To step, press the backslash (`\`) key.

To use a custom configuration Python script, run `python main.py <module-name>` (or `python3 main.py <module-name>`).
`<module-name>` is the name of the Python script in module name form; for example if your configuration file is in `configs/config_main.py`, then `<module-name>` will be `configs.config_main`.

# Images
This emulator uses images extracted from the ES PLUS emulators. To get them, you need to open the emulator EXE (`<model> Emulator.exe`) and DLL (`fxESPLUS_P<num>.dll`) in a program like [7-Zip](https://7-zip.org) or [Resource Hacker](http://angusj.com/resourcehacker).
- For the interface, you need to extract bitmap **3001** from the emulator **DLL**.
- For the status bar, you need to extract bitmap **135** from the emulator **EXE**.
