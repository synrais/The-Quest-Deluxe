"""The original game in DOSBox: a scratch copy of the DOS files, the emulator, keys sent to it, and a look at its memory.

The files in dos/TheQuest are the original and are never written to: each session runs in a scratch copy that is thrown away, and the
originals are checked against dos/MANIFEST.sha256 before and after.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORIGINAL = os.path.join(ROOT, 'dos', 'TheQuest')
MANIFEST = os.path.join(ROOT, 'dos', 'MANIFEST.sha256')
WINDOWS = sys.platform.startswith('win')

CONF = """[sdl]
fullscreen=false
windowresolution={w}x{h}
output=surface
autolock=false
[dosbox]
machine=vgaonly
[cpu]
core=normal
cycles={cycles}
[mixer]
nosound=true
[sblaster]
sbtype=none
[speaker]
pcspeaker=false
[autoexec]
mount c "{path}"
c:
TheQuest.exe
"""


def digest(root: str = ORIGINAL) -> dict:
    out = {}
    for base, _, files in os.walk(root):
        for f in sorted(files):
            p = os.path.join(base, f)
            h = hashlib.sha256()
            with open(p, 'rb') as fh:
                h.update(fh.read())
            out[os.path.relpath(p, root).replace('\\', '/')] = h.hexdigest()
    return out


def write_manifest():
    with open(MANIFEST, 'w', encoding='utf-8') as fh:
        for k, v in sorted(digest().items()):
            fh.write(f'{v}  {k}\n')


def manifest_ok() -> list:
    """The original files that are not as they were (empty when all are untouched)."""
    want = {}
    with open(MANIFEST, encoding='utf-8') as fh:
        for line in fh:
            if line.strip():
                v, k = line.rstrip('\n').split('  ', 1)
                want[k] = v
    have = digest()
    return sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))


def find_dosbox() -> str | None:
    """The DOSBox that comes with the pack (dos/dosbox), else one installed on the machine."""
    names = ['dosbox.exe'] if WINDOWS else ['dosbox']
    for n in names:
        for sub in ('dosbox', os.path.join('dosbox', 'bin')):
            p = os.path.join(ROOT, 'dos', sub, n)
            if os.path.isfile(p):
                return p
    for n in ['dosbox', 'dosbox-staging', 'dosbox-x']:
        p = shutil.which(n)
        if p:
            return p
    return None


class Dos:
    """One run of the original. `with Dos() as d:` then d.start(); d.key('Down') ..."""

    def __init__(self, size=(640, 480), cycles='fixed 30000', env=None):
        self.size, self.cycles = size, cycles
        self.env = dict(os.environ if env is None else env)
        self.scratch = None
        self.proc = None
        self.window = None
        self._mem = None
        self.base = None
        self.exe = find_dosbox()

    # ── life ────────────────────────────────────────────────────────────────
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.stop()

    def prepare(self):
        """A scratch copy of the original (the original itself is never run)."""
        bad = manifest_ok()
        if bad:
            raise RuntimeError('The original DOS files in dos/TheQuest have been changed: ' + ', '.join(bad[:5]))
        self.scratch = tempfile.mkdtemp(prefix='quest_dos_')
        shutil.copytree(ORIGINAL, os.path.join(self.scratch, 'game'))
        return os.path.join(self.scratch, 'game')

    @property
    def game_dir(self):
        return os.path.join(self.scratch, 'game')

    def start(self, wait=6.0):
        if self.exe is None:
            raise RuntimeError('DOSBox was not found (it belongs in dos/dosbox).')
        if self.scratch is None:
            self.prepare()
        conf = os.path.join(self.scratch, 'dosbox.conf')
        with open(conf, 'w', encoding='utf-8') as fh:
            fh.write(CONF.format(w=self.size[0], h=self.size[1], cycles=self.cycles, path=self.game_dir))
        env = dict(self.env, SDL_AUDIODRIVER='dummy')
        if WINDOWS:
            env['SDL_VIDEODRIVER'] = 'windib'              # plain Windows drawing: its window can be photographed and takes posted keys
        self.proc = subprocess.Popen([self.exe, '-conf', conf, '-noconsole'] if WINDOWS else [self.exe, '-conf', conf], env=env,
                                     cwd=self.scratch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # (it writes stdout.txt where it runs)
        t = time.time()
        while time.time() - t < wait:
            self.window = self._find_window()
            if self.window:
                break
            time.sleep(0.2)
        time.sleep(1.0)
        self.focus()

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self._mem:
            try:
                self._mem.close()
            except OSError:
                pass
            self._mem = None
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.scratch:
            shutil.rmtree(self.scratch, ignore_errors=True)
            self.scratch = None
        bad = manifest_ok()
        if bad:
            raise RuntimeError('The original DOS files were changed: ' + ', '.join(bad[:5]))

    # ── the window and its keys ─────────────────────────────────────────────
    def _x(self, *args):
        r = subprocess.run(['xdotool', *args], env=self.env, capture_output=True, text=True)
        return r.stdout.strip()

    def _find_window(self):
        if WINDOWS:
            return _win_find(self.proc.pid)
        ids = self._x('search', '--pid', str(self.proc.pid)).split() + self._x('search', '--name', 'DOSBox').split()
        for i in dict.fromkeys(ids):                          # the one that is the picture (some are only helpers of the toolkit)
            m = re.search(r'Geometry: (\d+)x(\d+)', self._x('getwindowgeometry', i))
            if m and int(m[1]) >= self.size[0] - 8 and int(m[2]) >= self.size[1] - 8:
                return i
        return None

    def focus(self):
        if not self.window:
            return
        if WINDOWS:
            _win_focus(self.window)
        else:
            self._x('windowfocus', self.window)

    def key(self, name: str, hold=0.04):
        """Press and let go of a key (an X key name such as 'Return', 'Up', 'y', 'space', 'Escape')."""
        if WINDOWS:
            _win_key(self.window, name, hold)
        else:
            back = self._x('getwindowfocus')                      # the window the person is typing in gets the keyboard back
            if back != self.window:
                self._x('windowfocus', self.window)
            self._x('keydown', name)
            time.sleep(hold)
            self._x('keyup', name)
            if back and back != self.window:
                self._x('windowfocus', back)

    def picture_bytes(self) -> bytes | None:
        """The window's pixels (PNG) without a file, to see whether the screen is still changing."""
        if not self.window:
            return None
        if WINDOWS:
            shot = _win_capture(self.window)
            return shot[2] if shot else None
        r = subprocess.run(['import', '-window', self.window, 'png:-'], env=self.env, capture_output=True)
        return r.stdout if r.returncode == 0 else None

    def key_and_wait(self, name: str, change_within=6.0, quiet=1.0, limit=25.0):
        """A key, then wait for the picture to change because of it, and to settle (menus and loading are slow, and a key sent too soon is lost)."""
        before = self.picture_bytes()
        self.key(name)
        t = time.time()
        while before is not None and time.time() - t < change_within and self.picture_bytes() == before:
            time.sleep(0.1)
        if WINDOWS and before is not None and self.picture_bytes() == before and os.environ.get('DOS_INPUT') != 'focus':
            os.environ['DOS_INPUT'] = 'focus'                  # posted keys did not reach it: bring DOSBox forward and type into it instead
            self.key(name)
            t = time.time()
            while time.time() - t < change_within and self.picture_bytes() == before:
                time.sleep(0.1)
        self.wait_still(quiet, limit)

    def wait_still(self, quiet=1.0, limit=15.0):
        """Wait until the picture has stopped changing for `quiet` seconds (or `limit` passes). Without pictures, just wait."""
        if not self.window or (WINDOWS and self.picture_bytes() is None):
            time.sleep(min(limit, quiet + 2))
            return
        t = time.time()
        last, since = None, time.time()
        while time.time() - t < limit:
            cur = self.picture_bytes()
            if cur != last:
                last, since = cur, time.time()
            elif time.time() - since >= quiet:
                return
            time.sleep(0.1)

    def screenshot(self, path: str) -> bool:
        if not self.window:
            return False
        if WINDOWS:
            shot = _win_capture(self.window)
            if not shot:
                return False
            import pygame
            pygame.image.save(shot[3], path)
            return True
        r = subprocess.run(['import', '-window', self.window, path], env=self.env, capture_output=True)
        return r.returncode == 0

    # ── its memory ──────────────────────────────────────────────────────────
    def _open_memory(self):
        if self._mem is not None:
            return
        if WINDOWS:
            self._mem = _WinMem(self.proc.pid)
            self.candidates = self._mem.find_all()
            self.base = self.candidates[-1][0]
            return
        self._mem = open(f'/proc/{self.proc.pid}/mem', 'rb', 0)
        self.candidates = []
        for line in open(f'/proc/{self.proc.pid}/maps'):
            m = re.match(r'([0-9a-f]+)-([0-9a-f]+) (\S+)', line)
            a, b = int(m[1], 16), int(m[2], 16)
            if m[3].startswith('rw') and 16 * 1024 * 1024 <= b - a < 40 * 1024 * 1024:
                self.candidates.append((a, b - a))
        if not self.candidates:
            raise RuntimeError('could not find the emulated memory of DOSBox')
        self.base = self.candidates[-1][0]

    def locate(self, address: int, marker: bytes) -> bool:
        """Point at the block of DOSBox's memory that is the DOS memory: the one with `marker` at `address`."""
        self._open_memory()
        if WINDOWS:
            return self.read(address, len(marker)) == marker
        for a, _ in self.candidates:
            self._mem.seek(a + address)
            try:
                if self._mem.read(len(marker)) == marker:
                    self.base = a
                    return True
            except (OSError, ValueError):
                pass
        return False

    def locate_text(self, marker: bytes) -> bool:
        """Find `marker` in DOS memory (the first 640 KB) and remember where: self.marker_at."""
        self._open_memory()
        if WINDOWS:
            for a, size in self.candidates:
                i = self._mem.read(a, size).find(marker)
                if i >= 0:
                    self.base, self.marker_at = a, i
                    return True
            return False
        for a, size in self.candidates:                        # (the DOS memory is not always at the start of the block)
            self._mem.seek(a)
            try:
                i = self._mem.read(size).find(marker)
            except (OSError, ValueError):
                continue
            if i >= 0:
                self.base, self.marker_at = a, i
                return True
        return False

    def read(self, address: int, n: int) -> bytes:
        """Bytes of DOS memory at a linear address (0 .. 1 MB)."""
        self._open_memory()
        if WINDOWS:
            return self._mem.read(self.base + address, n)
        self._mem.seek(self.base + address)
        return self._mem.read(n)

    def write(self, address: int, data: bytes) -> bool:
        """Put bytes into DOS memory (to set the original's random number state). False when the system will not allow it."""
        self._open_memory()
        try:
            if WINDOWS:
                return self._mem.write(self.base + address, data)
            with open(f'/proc/{self.proc.pid}/mem', 'r+b', 0) as fh:
                fh.seek(self.base + address)
                fh.write(data)
            return True
        except (OSError, ValueError):
            return False

    def snapshot(self, size=0xA0000) -> bytes:
        return self.read(0, size)


# ── Windows (written from the API's documentation: the Studio's "Check it works" says what does and does not work on the machine) ──
def _win_find(pid):
    """DOSBox's window: the visible top-level window of that process whose title starts with DOSBox."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(h, _):
        owner = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(owner))
        if owner.value == pid and u.IsWindowVisible(h) and _win_title(h).lower().startswith('dosbox'):
            found.append(h)
        return True
    u.EnumWindows(each, 0)
    return found[0] if found else None


def _win_title(h):
    import ctypes
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetWindowTextW(h, buf, 256)
    return buf.value


def _win_focus(h):
    import ctypes
    u = ctypes.windll.user32
    if u.IsIconic(h):
        u.ShowWindow(h, 9)                                        # SW_RESTORE
    u.SetForegroundWindow(h)


def _win_capture(h):
    """(width, height, raw pixels, a 640 x 480 pygame surface) of the window's client area, or None. GDI copy of the window's own drawing."""
    import ctypes
    from ctypes import wintypes
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    if not u.GetClientRect(h, ctypes.byref(rect)):
        return None
    w, hh = rect.right - rect.left, rect.bottom - rect.top
    if w < 100 or hh < 100:
        return None

    class BIH(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD), ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)]
    u.GetDC.restype = wintypes.HDC
    g.CreateCompatibleDC.restype = wintypes.HDC
    g.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    g.SelectObject.restype = wintypes.HGDIOBJ
    for fn, args in ((g.CreateCompatibleDC, [wintypes.HDC]), (g.CreateCompatibleBitmap, [wintypes.HDC, ctypes.c_int, ctypes.c_int]),
                     (g.SelectObject, [wintypes.HDC, wintypes.HGDIOBJ]), (g.DeleteObject, [wintypes.HGDIOBJ]), (g.DeleteDC, [wintypes.HDC]),
                     (u.GetDC, [wintypes.HWND]), (u.ReleaseDC, [wintypes.HWND, wintypes.HDC]),
                     (g.BitBlt, [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]),
                     (u.PrintWindow, [wintypes.HWND, wintypes.HDC, wintypes.UINT])):
        fn.argtypes = args
    hdc = u.GetDC(h)
    if not hdc:
        return None
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh)
    old = g.SelectObject(mdc, bmp)
    info = BIH(ctypes.sizeof(BIH), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)

    def grab(how):
        if how == 'blt':
            g.BitBlt(mdc, 0, 0, w, hh, hdc, 0, 0, 0x00CC0020)                 # SRCCOPY
        else:
            u.PrintWindow(h, mdc, 1)                                          # PW_CLIENTONLY
        g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(info), 0)
        return any(buf.raw[i] for i in range(0, w * hh * 4, 4099))            # not all black
    ok = grab('blt') or grab('print')
    g.SelectObject(mdc, old)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    if not ok:
        return None
    import pygame
    shot = pygame.image.frombuffer(buf.raw, (w, hh), 'BGRA').convert()
    if (w, hh) != (640, 480):
        shot = pygame.transform.scale(shot, (640, 480))
    return w, hh, buf.raw, shot


VK = {'Insert': 0x2D, 'Return': 0x0D, 'Escape': 0x1B, 'space': 0x20, 'Up': 0x26, 'Down': 0x28, 'Left': 0x25, 'Right': 0x27, 'BackSpace': 0x08,
      'Tab': 0x09, 'Delete': 0x2E, 'Home': 0x24, 'End': 0x23, 'Prior': 0x21, 'Next': 0x22}


def _win_key(h, name, hold):
    """Post the key to DOSBox's window, so our own window keeps the keyboard (DOS_INPUT=focus: bring DOSBox forward and use keybd_event)."""
    import ctypes
    u = ctypes.windll.user32
    vk = VK.get(name) or (u.VkKeyScanW(ord(name)) & 0xFF if len(name) == 1 else 0)
    sc = u.MapVirtualKeyW(vk, 0)
    ext = 1 if name in ('Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Prior', 'Next', 'Delete', 'Insert') else 0
    if os.environ.get('DOS_INPUT') == 'focus':
        _win_focus(h)
        u.keybd_event(vk, sc, ext, 0)
        time.sleep(hold)
        u.keybd_event(vk, sc, ext | 2, 0)
        return
    down = 1 | (sc << 16) | (ext << 24)
    u.PostMessageW(h, 0x0100, vk, down)                     # WM_KEYDOWN
    time.sleep(hold)
    u.PostMessageW(h, 0x0101, vk, down | 0xC0000000)        # WM_KEYUP


class _WinMem:
    """DOSBox's memory, read (and the dice written) through the Windows process calls. A program may do this to a process it started itself, as an
    ordinary user (no administrator needed); if Windows says no, the message says so."""

    def __init__(self, pid):
        import ctypes
        from ctypes import wintypes
        k = self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        k.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        k.VirtualQueryEx.restype = ctypes.c_size_t
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        self.pid = pid
        self.h = k.OpenProcess(0x0410, False, pid)                # query information, read memory
        if not self.h:
            err = ctypes.get_last_error()
            raise RuntimeError(f'Windows would not let this program look at DOSBox (error {err}'
                               + ('; access denied: is the Studio or DOSBox running as administrator, or is a security program blocking it?)' if err == 5 else ')'))

    def find_all(self):
        """[(address, size)] of the committed blocks of 16 to 40 MB: the emulated DOS memory is one of them."""
        import ctypes
        from ctypes import wintypes

        class MBI(ctypes.Structure):
            _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p), ('AllocationProtect', wintypes.DWORD),
                        ('PartId', wintypes.WORD), ('RegionSize', ctypes.c_size_t), ('State', wintypes.DWORD), ('Protect', wintypes.DWORD),
                        ('Type', wintypes.DWORD)]
        addr, mbi, found = 0, MBI(), []
        while self.k.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            if mbi.State == 0x1000 and 16 * 1024 * 1024 <= mbi.RegionSize < 40 * 1024 * 1024 and not mbi.Protect & 0x101:
                found.append((mbi.BaseAddress, mbi.RegionSize))           # (committed, and not no-access / guard pages)
            addr = (mbi.BaseAddress or 0) + mbi.RegionSize
            if addr >= 1 << 47:
                break
        if not found:
            raise RuntimeError('could not find the emulated memory of DOSBox')
        return found

    def read(self, address, n):
        import ctypes
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        self.k.ReadProcessMemory(self.h, ctypes.c_void_p(address), buf, n, ctypes.byref(got))
        return buf.raw[:got.value]

    def write(self, address, data):
        import ctypes
        from ctypes import wintypes
        self.k.OpenProcess.restype = wintypes.HANDLE
        h = self.k.OpenProcess(0x0038, False, self.pid)               # query, write and operate on memory
        if not h:
            return False
        done = ctypes.c_size_t()
        ok = self.k.WriteProcessMemory(h, ctypes.c_void_p(address), bytes(data), len(data), ctypes.byref(done))
        self.k.CloseHandle(h)
        return bool(ok) and done.value == len(data)

    def close(self):
        self.k.CloseHandle(self.h)


# ── the random numbers ──────────────────────────────────────────────────────────────────────────────────────────────────────
def lcg(s: int) -> int:
    """Borland C's rand() state step."""
    return (s * 22695477 + 1) & 0xFFFFFFFF


def find_changed_lcg(a: bytes, b: bytes, steps=400, align=2):
    """Offsets in two snapshots that hold a 32-bit value moved on by 1..steps rand() steps: [(offset, steps)]."""
    out = []
    n = len(a) - 4
    for off in range(0, n, align):
        x = a[off:off + 4]
        y = b[off:off + 4]
        if x == y:
            continue
        s = struct.unpack('<I', x)[0]
        t = struct.unpack('<I', y)[0]
        if s == 0:
            continue
        for k in range(1, steps + 1):
            s = lcg(s)
            if s == t:
                out.append((off, k))
                break
    return out
