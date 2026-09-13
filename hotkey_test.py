# Hotkey diagnostic test - press Ctrl+Shift+B within 15 seconds
import sys
import threading
import time

HOTKEY = "ctrl+shift+b"
match = threading.Event()

def on_hotkey():
    match.set()
    print("HOTKEY_TRIGGERED: Ctrl+Shift+B was pressed!", flush=True)

try:
    import keyboard
except ImportError as e:
    print("ERROR: keyboard not installed:", e)
    sys.exit(2)

print("Registering hotkey:", HOTKEY)
keyboard.add_hotkey(HOTKEY, on_hotkey)
print("Hotkey registered. Please press Ctrl+Shift+B within 15 seconds...", flush=True)

# Also try a plain listener method
start = time.time()
while time.time() - start < 15:
    time.sleep(0.1)
    if match.is_set():
        print("SUCCESS: Hotkey worked via keyboard library.")
        keyboard.unhook_all_hotkeys()
        sys.exit(0)

print("NO_MATCH: No hotkey pressed in 15s. The 'keyboard' library may not be"
      " capturing keys on this system (elevation/permission issue).")
# Now try testing with pynput as fallback
try:
    from pynput import keyboard as pk
    print("Trying pynput listener fallback for 15s...", flush=True)
    def on_press(key):
        try:
            if key == pk.Key.ctrl_l or key == pk.Key.ctrl_r:
                pass
            if key == pk.KeyCode.from_char(char='b') and any(
                k in [pk.Key.ctrl] for k in []
            ):
                pass
        except Exception:
            pass
    def on_release(key):
        if key == pk.Key.esc:
            return False
    with pk.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join(15)
    print("pynput listener finished without ctrl combo match.")
except Exception as e:
    print("pynput also failed:", e)

sys.exit(1)
