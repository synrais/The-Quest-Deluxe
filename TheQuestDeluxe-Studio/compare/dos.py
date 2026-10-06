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
    if os.environ.get('QUEST_NO_DOSBOX'):
        return None                                    # (for the test of what happens without it)
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
        self._job = None
        self.idle = lambda: None                      # called all the while this waits (the compare window answers Windows with it)

    def _sleep(self, seconds: float):
        """Sleep, but in short slices, calling idle() between them: a window that is not answering Windows for a few seconds is shown as stuck."""
        end = time.time() + seconds
        while True:
            self.idle()
            left = end - time.time()
            if left <= 0:
                return
            time.sleep(min(0.05, left))

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
            env['__COMPAT_LAYER'] = 'HIGHDPIAWARE'         # Windows must not stretch its window on a scaled screen (its picture would no longer be pixel for pixel)
            env['SDL_VIDEODRIVER'] = 'windib'              # plain Windows drawing: its window can be photographed and takes posted keys
        self.proc = subprocess.Popen([self.exe, '-conf', conf, '-noconsole'] if WINDOWS else [self.exe, '-conf', conf], env=env,
                                     cwd=self.scratch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,   # (it writes stdout.txt where it runs)
                                     **({} if WINDOWS else {'preexec_fn': _die_with_parent}))
        if WINDOWS:
            self._job = _win_job(self.proc)                    # DOSBox ends when this program does, however it ends
        t = time.time()
        while time.time() - t < wait:
            self.window = self._find_window()
            if self.window:
                break
            self._sleep(0.2)
        self._sleep(1.0)
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

    def embed(self, parent, x: int, y: int) -> bool:
        """Put DOSBox's window inside another window (the compare window), at (x, y) in it, with no frame of its own: the two are then one window,
        which moves, hides and closes together. `parent` is that window's handle (pygame.display.get_wm_info()['window']). False when it could not be done."""
        if not self.window or not parent:
            return False
        try:
            ok = _win_embed(self.window, parent, x, y) if WINDOWS else _x11_embed(self.window, parent, x, y)
        except (OSError, AttributeError, ValueError):
            ok = False
        self.parent = parent if ok else None
        return ok

    def picture_surface(self):
        """The original's screen as a pygame surface (None when it cannot be taken)."""
        if not self.window:
            return None
        if WINDOWS:
            shot = _win_capture(self.window)
            return shot[3] if shot else None
        return None

    def tuck_behind(self, our_window, x_in_ours: int = 640, y_in_ours: int = 0) -> bool:
        """Windows, when DOSBox cannot be locked into the compare window: it sits exactly behind the right half of ours (on the screen, never minimised or
        off it, so it is still drawn and can be copied), and the compare window shows its picture there."""
        if not WINDOWS or self.proc is None:
            return False
        h = _win_find(self.proc.pid)
        if not h:
            return False
        self.window = h
        u = _api()[0]
        if u.IsIconic(h):
            u.ShowWindow(h, 4)                                              # SW_SHOWNOACTIVATE: not minimised
        rect = _win_rect(our_window)
        if rect is None:
            return False
        u.SetWindowPos(h, our_window, rect[0] + x_in_ours, rect[1] + y_in_ours, 0, 0, 0x0001 | 0x0010)   # SWP_NOSIZE | NOACTIVATE, just below ours
        return True

    def show_beside(self, our_window) -> bool:
        """Windows, when its picture cannot be copied in: DOSBox is put in front, to the right of ours, so the original can always be seen."""
        if not WINDOWS or self.proc is None:
            return False
        h = _win_find(self.proc.pid)
        rect = _win_rect(our_window)
        if not h or rect is None:
            return False
        self.window = h
        u = _api()[0]
        u.ShowWindow(h, 9)                                                  # SW_RESTORE
        u.SetWindowPos(h, None, rect[2] + 8, rect[1], 0, 0, 0x0001 | 0x0004 | 0x0040)   # SWP_NOSIZE | NOZORDER | SHOWWINDOW
        return True

    def keep_embedded(self, x: int, y: int) -> bool:
        """Called now and then: DOSBox may make itself a new window when the game changes screen mode (a new window is a new top-level one, outside ours);
        find it again and lock it in. True when it had to."""
        if not WINDOWS or not getattr(self, 'parent', None) or self.proc is None:
            return False
        h = _win_find(self.proc.pid)
        if h is None:
            return False
        u = _api()[0]
        if h != self.window or u.GetParent(h) != self.parent:
            self.window = h
            return _win_embed(h, self.parent, x, y)
        return False

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
            shot = _win_capture(self.window, want_surface=False)
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
                self._sleep(0.1)
        self.wait_still(quiet, limit)

    def wait_still(self, quiet=1.0, limit=15.0):
        """Wait until the picture has stopped changing for `quiet` seconds (or `limit` passes). Without pictures, just wait."""
        if not self.window or (WINDOWS and self.picture_bytes() is None):
            self._sleep(min(limit, quiet + 2))
            return
        t = time.time()
        last, since = None, time.time()
        while time.time() - t < limit:
            cur = self.picture_bytes()
            if cur != last:
                last, since = cur, time.time()
            elif time.time() - since >= quiet:
                return
            self._sleep(0.1)

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


_API = []


def _api():
    """(user32, gdi32) with the types of every call declared. A window handle is 64 bits wide on a 64-bit Windows, and ctypes passes a plain number as
    a 32-bit int unless told otherwise ("int too long to convert"), so nothing here is called without its types."""
    if not _API:
        import ctypes
        from ctypes import wintypes as w
        u, g = ctypes.WinDLL('user32', use_last_error=True), ctypes.WinDLL('gdi32', use_last_error=True)
        proto = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        for lib, name, args, res in (
                (u, 'EnumWindows', [proto, w.LPARAM], w.BOOL), (u, 'GetWindowThreadProcessId', [w.HWND, ctypes.POINTER(w.DWORD)], w.DWORD),
                (u, 'IsWindowVisible', [w.HWND], w.BOOL), (u, 'GetWindowTextW', [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int),
                (u, 'GetParent', [w.HWND], w.HWND), (u, 'GetForegroundWindow', [], w.HWND), (u, 'AttachThreadInput', [w.DWORD, w.DWORD, w.BOOL], w.BOOL), (u, 'IsIconic', [w.HWND], w.BOOL), (u, 'ShowWindow', [w.HWND, ctypes.c_int], w.BOOL), (u, 'SetForegroundWindow', [w.HWND], w.BOOL),
                (u, 'GetClientRect', [w.HWND, ctypes.POINTER(w.RECT)], w.BOOL), (u, 'GetDC', [w.HWND], w.HDC), (u, 'ReleaseDC', [w.HWND, w.HDC], ctypes.c_int),
                (u, 'PrintWindow', [w.HWND, w.HDC, w.UINT], w.BOOL), (u, 'PostMessageW', [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
                (u, 'SetWindowPos', [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT], w.BOOL),
                (u, 'MapVirtualKeyW', [w.UINT, w.UINT], w.UINT), (u, 'VkKeyScanW', [w.WCHAR], ctypes.c_short),
                (u, 'keybd_event', [w.BYTE, w.BYTE, w.DWORD, ctypes.c_size_t], None),
                (g, 'CreateCompatibleDC', [w.HDC], w.HDC), (g, 'CreateCompatibleBitmap', [w.HDC, ctypes.c_int, ctypes.c_int], w.HBITMAP),
                (g, 'SelectObject', [w.HDC, w.HGDIOBJ], w.HGDIOBJ), (g, 'DeleteObject', [w.HGDIOBJ], w.BOOL), (g, 'DeleteDC', [w.HDC], w.BOOL),
                (g, 'BitBlt', [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, w.DWORD], w.BOOL),
                (g, 'GetDIBits', [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT], ctypes.c_int)):
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = args, res
        _API.extend([u, g])
    return _API[0], _API[1]


def _die_with_parent():
    """Linux, in the new DOSBox process: be killed when the process that started it ends (closed, asked to stop or killed): no DOSBox is left behind."""
    import ctypes
    import signal
    try:
        ctypes.CDLL('libc.so.6').prctl(1, int(signal.SIGKILL))          # PR_SET_PDEATHSIG
    except (OSError, AttributeError):
        pass


def _win_job(proc):
    """Windows: put the process in a job that kills everything in it when its last handle closes, which happens when this program ends for any reason."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL('kernel32', use_last_error=True)

    class Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', wintypes.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ('Read', 'Write', 'Other', 'ReadBytes', 'WriteBytes', 'OtherBytes')]

    class Extended(ctypes.Structure):
        _fields_ = [('Basic', Basic), ('Io', IoCounters), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = k.CreateJobObjectW(None, None)
    if not job:
        return None
    info = Extended()
    info.Basic.LimitFlags = 0x2000                                          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    k.AssignProcessToJobObject(job, int(proc._handle))
    return job


def _x11_embed(child, parent, x, y):
    """X11: reparent the window into the parent's window (the parent's own drawing leaves its children alone)."""
    import ctypes
    import ctypes.util
    lib = ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XReparentWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
    lib.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = lib.XOpenDisplay(None)
    if not display:
        return False
    try:
        lib.XReparentWindow(display, int(child), int(parent), x, y)
        lib.XMapWindow(display, int(child))
        lib.XSync(display, 0)
    finally:
        lib.XCloseDisplay(display)
    return True


def _win_embed(child, parent, x, y):
    """Windows: make DOSBox's window a child of the parent's, without its frame, at (x, y); the parent leaves its children's area alone."""
    import ctypes
    u = _api()[0]
    GWL_STYLE, WS_CHILD, WS_VISIBLE, WS_CLIPCHILDREN, WS_CLIPSIBLINGS = -16, 0x40000000, 0x10000000, 0x02000000, 0x04000000
    u.GetWindowLongPtrW.argtypes, u.GetWindowLongPtrW.restype = [ctypes.c_void_p, ctypes.c_int], ctypes.c_ssize_t
    u.SetWindowLongPtrW.argtypes, u.SetWindowLongPtrW.restype = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t
    u.SetParent.argtypes, u.SetParent.restype = [ctypes.c_void_p, ctypes.c_void_p], ctypes.c_void_p
    u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    style = u.GetWindowLongPtrW(parent, GWL_STYLE)
    u.SetWindowLongPtrW(parent, GWL_STYLE, style | WS_CLIPCHILDREN)
    u.SetParent(child, parent)
    u.SetWindowLongPtrW(child, GWL_STYLE, WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS)       # no title bar, no frame
    u.SetWindowPos(child, None, x, y, 0, 0, 0x0001 | 0x0004 | 0x0020 | 0x0040)             # SWP_NOSIZE | NOZORDER | FRAMECHANGED | SHOWWINDOW
    return u.GetParent(child) == parent                                                     # did it take?


# ── Windows (written from the API's documentation: the Studio's "Check it works" says what does and does not work on the machine) ──
def _win_find(pid, prefix='dosbox'):
    """A window of a process: its visible top-level window whose title starts with `prefix` (DOSBox's own by default)."""
    import ctypes
    from ctypes import wintypes
    u, _g = _api()
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(h, _):
        owner = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(owner))
        if owner.value == pid and u.IsWindowVisible(h) and _win_title(h).lower().startswith(prefix):
            found.append(h)
        return True
    u.EnumWindows(each, 0)
    return found[0] if found else None


def _win_title(h):
    import ctypes
    buf = ctypes.create_unicode_buffer(256)
    _api()[0].GetWindowTextW(h, buf, 256)
    return buf.value


def _win_focus(h):
    u = _api()[0]
    if u.IsIconic(h):
        u.ShowWindow(h, 9)                                        # SW_RESTORE
    u.SetForegroundWindow(h)


def _win_rect(h):
    """(left, top, right, bottom) of a window on the screen."""
    import ctypes
    from ctypes import wintypes
    rect = wintypes.RECT()
    u = _api()[0]
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    if not u.GetWindowRect(h, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def bring_to_front(h):
    """Windows: put a window in front and give it the keyboard. A program started by another one is often left behind it (Windows does not let a program take
    the front just because it started); the topmost-then-not trick, and attaching to the input of the window that has the front, get past that."""
    import ctypes
    from ctypes import wintypes
    u = _api()[0]
    u.ShowWindow(h, 9)                                                      # SW_RESTORE
    u.SetWindowPos(h, ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)      # HWND_TOPMOST, no move or size, shown
    u.SetWindowPos(h, ctypes.c_void_p(-2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)      # then HWND_NOTOPMOST: it stays in front of the others
    front = u.GetForegroundWindow()
    k = ctypes.WinDLL('kernel32')
    me, other = k.GetCurrentThreadId(), u.GetWindowThreadProcessId(front, None) if front else 0
    if other and other != me:
        u.AttachThreadInput(me, other, True)
        u.SetForegroundWindow(h)
        u.AttachThreadInput(me, other, False)
    else:
        u.SetForegroundWindow(h)


_CAPTURE = {'how': None, 'size': None}                       # which way of copying worked (kept: the first is tried first), and the size seen


def _win_capture(h, want_surface=True):
    """(width, height, raw pixels, a 640 x 480 pygame surface) of the window's client area, or None. GDI copy of the window's own drawing."""
    import ctypes
    from ctypes import wintypes
    u, g = _api()
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
            u.PrintWindow(h, mdc, 3)                                          # PW_CLIENTONLY | PW_RENDERFULLCONTENT (works while it is behind another window)
        g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(info), 0)
        return any(buf.raw[i] for i in range(0, w * hh * 4, 4099))            # not all black
    order = ['blt', 'print'] if _CAPTURE['how'] != 'print' else ['print', 'blt']
    ok = False
    for how in order:
        if grab(how):
            ok, _CAPTURE['how'] = True, how
            break
    _CAPTURE['size'] = (w, hh)
    g.SelectObject(mdc, old)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    if not ok:
        return None
    if not want_surface:
        return w, hh, buf.raw, None                                          # (just the bytes: to see whether the picture is changing)
    import pygame
    raw = bytearray(buf.raw)
    raw[3::4] = b'\xff' * (w * hh)                                           # GDI leaves the alpha bytes empty: the picture is opaque
    shot = pygame.image.frombuffer(bytes(raw), (w, hh), 'BGRA')
    if pygame.display.get_surface():
        shot = shot.convert()
    if (w, hh) != (640, 480):
        shot = pygame.transform.scale(shot, (640, 480))
    return w, hh, buf.raw, shot


VK = {'Insert': 0x2D, 'Return': 0x0D, 'Escape': 0x1B, 'space': 0x20, 'Up': 0x26, 'Down': 0x28, 'Left': 0x25, 'Right': 0x27, 'BackSpace': 0x08,
      'Tab': 0x09, 'Delete': 0x2E, 'Home': 0x24, 'End': 0x23, 'Prior': 0x21, 'Next': 0x22}


def _win_key(h, name, hold):
    """Post the key to DOSBox's window, so our own window keeps the keyboard (DOS_INPUT=focus: bring DOSBox forward and use keybd_event)."""
    u = _api()[0]
    vk = VK.get(name) or (u.VkKeyScanW(name) & 0xFF if len(name) == 1 else 0)
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
