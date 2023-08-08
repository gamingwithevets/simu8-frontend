This is a **frontend** for [LifeEmu](https://github.com/LifeEmu)'s [SimU8](https://github.com/SimU8) emulator written in Python. It's a very simple Tkinter window with Pygame embedded into it.

Currently, LifeEmu's emulator is unfinished, therefore the frontend may look like it isn't working properly. However, the screen **has been tested and verified to be working** via direct memory editing.

# How to use
Because SimU8 was written in C and this frontend was written in Python, a **shared library** is needed to use the frontend.
That's not really a big deal, however I thought I should mention it, as C compilers are usually used for compiling binaries and not shared libraries.

1. Clone the **`drivers`** branch of the SimU8 repository:
```
git clone https://github.com/SimU8.git
git checkout drivers
```
If you don't have `git` installed you can just download a ZIP file and extract it.

2. Place yourself in the root of the SimU8 repo and run:
```
gcc src/core.c src/mmu.c -O3 -fPIC -shared -o simu8.so
```
On Windows you can use `gcc` on MingW or Cygwin.  
If no errors appear, a `simu8.so` file should appear.

3. Now clone this repository:
```
git clone https://github.com/gamingwithevets/simu8-frontend.git
```
4. Edit the `config.py` file as needed.
5. Run `python main.py` (or `python3 main.py`) and you're done.
