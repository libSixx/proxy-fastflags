import json
import requests
import dearpygui.dearpygui as dpg
import urllib3
import keyboard
import time
import threading
import random
from tkinter import Tk, filedialog
import pyperclip
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Constants ─────────────────────────────────────────────────────────────────
CONFIG_FILE        = "config.json"
DEFAULT_FLAGS_FILE = os.path.join("ClientSettings", "ClientAppSettings.json")
FLAGS_URL          = (
    "https://raw.githubusercontent.com/MaximumADHD/"
    "Roblox-Client-Tracker/refs/heads/roblox/FVariables.txt"
)

MATRIX_CHARS   = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*+-=/<>"
CHAR_W, CHAR_H = 10, 15
MATRIX_COLS    = 57
MATRIX_ROWS    = 40
MATRIX_W       = MATRIX_COLS * CHAR_W   # 570 px
MATRIX_H       = MATRIX_ROWS * CHAR_H   # 600 px
LOG_COLOR      = [100, 255, 180]

# ── Runtime state ─────────────────────────────────────────────────────────────
keybinds           = {}
is_setting_keybind = False
last_keybind_time  = 0.0
last_matrix_t      = 0.0
console_log        = []
selected_flag      = None

matrix_drops  = [random.randint(0, MATRIX_ROWS) for _ in range(MATRIX_COLS)]
matrix_trails = [[] for _ in range(MATRIX_COLS)]


# =============================================================================
# FILE AUTO-CREATION
# =============================================================================
def ensure_required_files() -> list:
    """Creates any missing files the app needs. Returns list of created paths."""
    created = []

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(
                {"json_path": DEFAULT_FLAGS_FILE, "always_on_top": False},
                f, indent=4
            )
        created.append(CONFIG_FILE)

    os.makedirs("ClientSettings", exist_ok=True)
    if not os.path.exists(DEFAULT_FLAGS_FILE):
        with open(DEFAULT_FLAGS_FILE, "w") as f:
            json.dump(
                {"dczSettings": {}, "disabledFlags": {},
                 "keybinds": {}, "flagOrder": []},
                f, indent=4
            )
        created.append(DEFAULT_FLAGS_FILE)

    return created


_created_files = ensure_required_files()

# ── Config ─────────────────────────────────────────────────────────────────────
with open(CONFIG_FILE, "r") as _f:
    _cfg = json.load(_f)
JSON_PATH     = _cfg.get("json_path", DEFAULT_FLAGS_FILE)
ALWAYS_ON_TOP = _cfg.get("always_on_top", False)


# =============================================================================
# CONSOLE LOG
# =============================================================================
def log(message: str):
    ts    = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {message}"
    console_log.append(entry)
    if len(console_log) > 300:
        console_log.pop(0)
    try:
        if dpg.does_item_exist("console_log_window"):
            dpg.add_text(entry, parent="console_log_window", color=LOG_COLOR)
            dpg.set_y_scroll(
                "console_log_window",
                dpg.get_y_scroll_max("console_log_window")
            )
    except Exception:
        pass


# =============================================================================
# JSON HELPERS
# =============================================================================
def load_json():
    try:
        with open(JSON_PATH, "r") as file:
            data = json.load(file)
        log(f"Loaded: {JSON_PATH}")
    except FileNotFoundError:
        data = {}
        log(f"File not found, starting fresh: {JSON_PATH}")
    except json.JSONDecodeError as e:
        data = {}
        log(f"JSON decode error: {e}")

    data.setdefault("dczSettings", {})
    data.setdefault("disabledFlags", {})
    data.setdefault("keybinds", {})
    if "flagOrder" not in data:
        data["flagOrder"] = (
            list(data["dczSettings"].keys())
            + list(data["disabledFlags"].keys())
        )
    return data, data["keybinds"]


def save_json(data):
    data["flagOrder"] = [
        f for f in data["flagOrder"]
        if f in data["dczSettings"] or f in data["disabledFlags"]
    ]
    data["keybinds"] = keybinds
    with open(JSON_PATH, "w") as file:
        json.dump(data, file, indent=4)


# =============================================================================
# REMOTE FLAG FETCH
# =============================================================================
def fetch_flags() -> list:
    log("Fetching flags from remote...")
    try:
        resp    = requests.get(FLAGS_URL, verify=False, timeout=10)
        allowed = ("DFInt", "DFFlag", "DFString")
        flags   = []
        for line in resp.text.split("\n"):
            if line.startswith(("[C++]", "[Lua]")) and " " in line:
                name = line.split(" ", 1)[1]
                if name.startswith(allowed):
                    flags.append(name)
        log(f"Fetched {len(flags)} flags.")
        return flags
    except Exception as e:
        log(f"Failed to fetch flags: {e}")
        return []


flags_list = fetch_flags()
settings, keybinds = load_json()

for _path in _created_files:
    log(f"Auto-created: {_path}")


# =============================================================================
# KEYBIND SYSTEM
# =============================================================================
def clear_keybind(sender, app_data, flag):
    keybinds.pop(flag, None)
    save_json(settings)
    dpg.configure_item(f"keybind_button_{flag}", label="Keybind: none")
    dpg.configure_item(f"clear_keybind_button_{flag}", show=False)
    log(f"Cleared keybind for {flag}")


def set_keybind(sender, app_data, flag):
    global is_setting_keybind, last_keybind_time
    if is_setting_keybind:
        return
    is_setting_keybind = True
    dpg.configure_item(f"keybind_button_{flag}", label="Keybind: waiting for input...")
    dpg.split_frame()

    def capture_key():
        global is_setting_keybind, last_keybind_time
        pressed_modifier = None
        while True:
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                pressed_key = event.name.upper()
                if pressed_key in ("CTRL", "SHIFT"):
                    pressed_modifier = pressed_key
                    continue
                modifier = ""
                if keyboard.is_pressed("ctrl"):
                    modifier = "CTRL + "
                elif keyboard.is_pressed("shift"):
                    modifier = "SHIFT + "
                combo = f"{modifier}{pressed_key}"
                keybinds[flag] = combo
                save_json(settings)
                dpg.configure_item(f"keybind_button_{flag}", label=f"Keybind: {combo}")
                dpg.configure_item(f"clear_keybind_button_{flag}", show=True)
                last_keybind_time  = time.time()
                is_setting_keybind = False
                log(f"Keybind set -> {flag}: {combo}")
                break
            elif event.event_type == keyboard.KEY_UP and pressed_modifier:
                keybinds[flag] = pressed_modifier
                save_json(settings)
                dpg.configure_item(f"keybind_button_{flag}", label=f"Keybind: {pressed_modifier}")
                dpg.configure_item(f"clear_keybind_button_{flag}", show=True)
                last_keybind_time  = time.time()
                is_setting_keybind = False
                log(f"Keybind set -> {flag}: {pressed_modifier}")
                break

    threading.Thread(target=capture_key, daemon=True).start()


def global_key_listener():
    pressed_keys = set()
    while True:
        event = keyboard.read_event()
        if is_setting_keybind:
            continue
        if event.event_type == keyboard.KEY_DOWN:
            pressed_key = event.name.upper()
            modifier    = ""
            if keyboard.is_pressed("ctrl"):
                modifier = "CTRL + "
            elif keyboard.is_pressed("shift"):
                modifier = "SHIFT + "
            full = f"{modifier}{pressed_key}"
            if full not in pressed_keys and pressed_key not in pressed_keys:
                pressed_keys.add(full)
                pressed_keys.add(pressed_key)
                for flag, key in keybinds.items():
                    if key in (full, pressed_key):
                        if dpg.does_item_exist(f"enabled_checkbox_{flag}"):
                            cur = dpg.get_value(f"enabled_checkbox_{flag}")
                            dpg.set_value(f"enabled_checkbox_{flag}", not cur)
                            toggle_flag_visibility(None, None, flag)
        elif event.event_type == keyboard.KEY_UP:
            rel     = event.name.upper()
            mod_key = f"CTRL + {rel}" if "CTRL" in pressed_keys else f"SHIFT + {rel}"
            pressed_keys.discard(rel)
            pressed_keys.discard(mod_key)


# =============================================================================
# FLAG MANAGEMENT
# =============================================================================
def save_flag(name, value):
    if name not in settings["flagOrder"]:
        settings["flagOrder"].append(name)
    if name in settings["disabledFlags"]:
        settings["disabledFlags"][name] = value
    else:
        settings["dczSettings"][name] = value
    save_json(settings)
    update_enabled_flags_list()
    log(f"Saved -> {name} = {value}")


def remove_flag(sender, app_data, flag):
    settings["dczSettings"].pop(flag, None)
    settings["disabledFlags"].pop(flag, None)
    if flag in settings["flagOrder"]:
        settings["flagOrder"].remove(flag)
    keybinds.pop(flag, None)
    save_json(settings)
    update_enabled_flags_list()
    log(f"Removed flag: {flag}")


def toggle_flag_visibility(sender, app_data, flag):
    if flag in settings["dczSettings"]:
        settings["disabledFlags"][flag] = settings["dczSettings"].pop(flag)
        log(f"Disabled: {flag}")
    else:
        settings["dczSettings"][flag] = settings["disabledFlags"].pop(flag)
        log(f"Enabled: {flag}")
    save_json(settings)
    update_enabled_flags_list()


def update_flag_value(sender, app_data, flag):
    new_value = dpg.get_value(f"edit_value_{flag}")
    if flag in settings["dczSettings"]:
        settings["dczSettings"][flag] = new_value
    elif flag in settings["disabledFlags"]:
        settings["disabledFlags"][flag] = new_value
    save_json(settings)
    dpg.set_value(f"edit_value_{flag}", "")
    dpg.configure_item(f"display_value_{flag}", default_value=f"{flag}: {new_value}")
    log(f"Updated -> {flag} = {new_value}")


# =============================================================================
# PATH / SETTINGS HELPERS
# =============================================================================
def update_json_path(sender, app_data):
    global JSON_PATH, settings, keybinds
    JSON_PATH = app_data
    with open(CONFIG_FILE, "w") as f:
        json.dump({"json_path": JSON_PATH, "always_on_top": ALWAYS_ON_TOP}, f)
    settings, keybinds = load_json()
    update_enabled_flags_list()


def select_json_file():
    global JSON_PATH, settings, keybinds
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file_path:
        JSON_PATH = file_path
        dpg.set_value("json_path_input", JSON_PATH)
        with open(CONFIG_FILE, "w") as f:
            json.dump({"json_path": JSON_PATH, "always_on_top": ALWAYS_ON_TOP}, f)
        settings, keybinds = load_json()
        update_enabled_flags_list()
        log(f"Switched to: {JSON_PATH}")


def toggle_always_on_top(sender, app_data):
    global ALWAYS_ON_TOP
    ALWAYS_ON_TOP = app_data
    dpg.configure_viewport(0, always_on_top=ALWAYS_ON_TOP)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"json_path": JSON_PATH, "always_on_top": ALWAYS_ON_TOP}, f)
    log(f"Always on top: {ALWAYS_ON_TOP}")


# =============================================================================
# UI LIST HELPERS
# =============================================================================
def update_search(sender, app_data):
    update_flag_list(app_data.lower())


def select_flag(sender, app_data, flag):
    global selected_flag
    selected_flag = flag
    dpg.set_value("selected_flag_text", f"Selected Flag: {flag}")
    log(f"Selected: {flag}")


def set_flag_value(sender, app_data):
    global selected_flag
    if selected_flag:
        new_value = dpg.get_value("flag_value_input")
        save_flag(selected_flag, new_value)
        dpg.set_value("flag_value_input", "")
        selected_flag = None
        dpg.set_value("selected_flag_text", "Selected Flag: None")


def update_flag_list(search_query=""):
    dpg.delete_item("available_flags_list", children_only=True)
    for flag in flags_list:
        if search_query in flag.lower():
            dpg.add_button(
                label=flag, parent="available_flags_list",
                callback=select_flag, user_data=flag
            )


def update_enabled_flags_list():
    existing = {
        flag: dpg.get_value(f"edit_value_{flag}")
        for flag in settings["flagOrder"]
        if dpg.does_item_exist(f"edit_value_{flag}")
    }
    dpg.delete_item("enabled_flags_list", children_only=True)
    settings["flagOrder"] = [
        f for f in settings["flagOrder"]
        if f in settings["dczSettings"] or f in settings["disabledFlags"]
    ]
    for index, flag in enumerate(settings["flagOrder"]):
        is_enabled    = flag in settings["dczSettings"]
        keybind_label = f"Keybind: {keybinds.get(flag, 'none')}"
        cur_val       = settings["dczSettings"].get(
            flag, settings["disabledFlags"].get(flag, "")
        )
        with dpg.group(parent="enabled_flags_list"):
            dpg.add_input_text(
                tag=f"display_value_{flag}",
                default_value=f"{flag}: {cur_val}",
                width=561, readonly=True
            )
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag=f"edit_value_{flag}", width=400, hint="enter new value..."
                )
                dpg.add_button(label="Update Value", callback=update_flag_value, user_data=flag)
            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    label="Enabled", default_value=is_enabled,
                    callback=toggle_flag_visibility, user_data=flag,
                    tag=f"enabled_checkbox_{flag}"
                )
                dpg.add_button(label="Remove", callback=remove_flag, user_data=flag)
                dpg.add_button(
                    label=keybind_label, callback=set_keybind,
                    user_data=flag, tag=f"keybind_button_{flag}"
                )
                dpg.add_button(
                    label="X", callback=clear_keybind, user_data=flag,
                    width=25, tag=f"clear_keybind_button_{flag}",
                    show=flag in keybinds
                )
            if index < len(settings["flagOrder"]) - 1:
                dpg.add_spacer(height=10)

    for flag, value in existing.items():
        if dpg.does_item_exist(f"edit_value_{flag}"):
            dpg.set_value(f"edit_value_{flag}", value)


# =============================================================================
# JSON IMPORT / EXPORT
# =============================================================================
def _set_feedback(text, color, clear_after=5):
    dpg.set_value("json_feedback", text)
    dpg.configure_item("json_feedback", color=color)
    threading.Timer(clear_after, lambda: dpg.set_value("json_feedback", "")).start()


def show_json_import_popup():
    if not dpg.does_item_exist("json_import_popup"):
        with dpg.window(
            label="Import JSON", modal=True, no_resize=True,
            no_close=True, no_collapse=True, tag="json_import_popup"
        ):
            dpg.add_text("Paste JSON here:")
            dpg.add_input_text(multiline=True, width=400, height=250, tag="json_input_text")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Import", callback=import_json_from_input)
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item("json_import_popup")
                )
    else:
        dpg.show_item("json_import_popup")


def import_json_from_input(sender, app_data):
    json_content = dpg.get_value("json_input_text")
    try:
        data = json.loads(json_content)
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure.")
        bad = [k for k in data if k not in flags_list]
        if bad:
            raise ValueError(f"Flags not in Available Flags: {', '.join(bad)}")
        for key, value in data.items():
            if isinstance(value, dict):
                raise ValueError("Nested JSON is not allowed.")
            if not key.startswith(("DFFlag", "DFInt", "DFString")):
                raise ValueError(f"Invalid key: {key}")
        for key, value in data.items():
            if key in settings["disabledFlags"]:
                settings["disabledFlags"][key] = value
            else:
                settings["dczSettings"][key] = value
            if key not in settings["flagOrder"]:
                settings["flagOrder"].append(key)
        save_json(settings)
        update_enabled_flags_list()
        _set_feedback("Import JSON: Successfully imported.", [0, 255, 0])
        dpg.delete_item("json_import_popup")
        log(f"Imported {len(data)} flags via JSON paste.")
    except (json.JSONDecodeError, ValueError) as e:
        _set_feedback(f"Import JSON: {e}", [255, 0, 0])
        log(f"Import failed: {e}")


def export_json(sender, app_data):
    export_data = {
        key: settings["dczSettings"].get(key, settings["disabledFlags"].get(key, ""))
        for key in settings["flagOrder"]
    }
    try:
        pyperclip.copy(json.dumps(export_data, indent=4))
        _set_feedback("Export JSON: Copied to clipboard.", [0, 255, 0])
        log(f"Exported {len(export_data)} flags to clipboard.")
    except Exception as e:
        _set_feedback(f"Export JSON: Failed ({e})", [255, 0, 0])
        log(f"Export failed: {e}")


# =============================================================================
# MATRIX RAIN  (driven by the main render loop)
# =============================================================================
def update_matrix():
    if not dpg.does_item_exist("matrix_drawlist"):
        return
    dpg.delete_item("matrix_drawlist", children_only=True)

    for x in range(MATRIX_COLS):
        matrix_trails[x].insert(0, matrix_drops[x])
        if len(matrix_trails[x]) > 6:
            matrix_trails[x].pop()

        for i, y in enumerate(matrix_trails[x]):
            if 0 <= y < MATRIX_ROWS:
                char = random.choice(MATRIX_CHARS)
                px   = x * CHAR_W + 1
                py   = y * CHAR_H + 1
                if i == 0:
                    color, size = [255, 100, 200, 255], 14  # hot-pink head
                elif i <= 2:
                    color, size = [200, 60, 170, 210], 13   # mid glow
                else:
                    color, size = [130, 30, 120, 140], 12   # fade trail
                dpg.draw_text(
                    (px, py), char, color=color, size=size,
                    parent="matrix_drawlist"
                )

        matrix_drops[x] += 1
        if matrix_drops[x] > MATRIX_ROWS and random.random() > 0.97:
            matrix_drops[x] = 0
            matrix_trails[x] = []


# =============================================================================
# STARTUP POPUP
# =============================================================================
def show_startup_popup():
    with dpg.window(
        label="bro really...", modal=True, no_resize=True,
        no_close=True, no_collapse=True, tag="startup_popup",
        width=345, pos=[130, 295]
    ):
        dpg.add_spacer(height=4)
        dpg.add_text("how u gon leak something that doesnt work lol")
        dpg.add_spacer(height=2)
        dpg.add_text("est. 2023", color=[160, 160, 160])
        dpg.add_spacer(height=8)
        dpg.add_button(
            label="ok bro my bad", width=-1,
            callback=lambda: dpg.delete_item("startup_popup")
        )
        dpg.add_spacer(height=4)


# =============================================================================
# MAIN
# =============================================================================
def main():
    global last_matrix_t

    dpg.create_context()
    dpg.create_viewport(title="Flag Browser", width=610, height=750, resizable=False)

    with dpg.window(
        label=" ", width=600, height=750,
        no_close=True, no_collapse=True, no_title_bar=True,
        no_move=True, no_resize=True, tag="main_window"
    ):
        with dpg.tab_bar():

            # ── Flag Browser ──────────────────────────────────────────────
            with dpg.tab(label="Flag Browser"):
                dpg.add_text("Available Flags")
                dpg.add_input_text(label="Search", callback=update_search)
                with dpg.child_window(height=200, tag="available_flags_list"):
                    update_flag_list()
                dpg.add_text("Selected Flag: None", tag="selected_flag_text")
                dpg.add_input_text(label="Value", tag="flag_value_input")
                dpg.add_button(label="Set Value", callback=set_flag_value)
                dpg.add_text("Modified Flags")
                with dpg.child_window(height=325, tag="enabled_flags_list"):
                    update_enabled_flags_list()

            # ── Settings tab ──────────────────────────────────────────────────
            with dpg.tab(label="Settings"):
                dpg.add_spacer(height=3)
                dpg.add_input_text(
                    label="JSON Path", default_value=JSON_PATH,
                    callback=update_json_path, readonly=True, tag="json_path_input"
                )
                dpg.add_button(label="Select File", callback=select_json_file)
                dpg.add_spacer(height=5)
                dpg.add_separator()
                dpg.add_spacer(height=5)
                dpg.add_checkbox(
                    label="Always On Top", default_value=ALWAYS_ON_TOP,
                    callback=toggle_always_on_top, tag="always_on_top_checkbox"
                )
                dpg.add_spacer(height=5)
                dpg.add_separator()
                dpg.add_spacer(height=5)
                dpg.add_button(label="Import JSON", callback=show_json_import_popup)
                dpg.add_spacer(height=2)
                dpg.add_button(label="Export JSON", callback=export_json)
                dpg.add_spacer(height=2)
                dpg.add_text("", tag="json_feedback")
                dpg.add_spacer(height=5)
                dpg.add_separator()
                dpg.add_spacer(height=5)
                # Console
                with dpg.group(horizontal=True):
                    dpg.add_text("Console Log")
                    dpg.add_spacer(width=8)
                    dpg.add_button(
                        label="Clear",
                        callback=lambda: (
                            console_log.clear(),
                            dpg.delete_item("console_log_window", children_only=True)
                        )
                    )
                dpg.add_spacer(height=3)
                with dpg.child_window(height=340, tag="console_log_window", border=True):
                    # Replay any logs that happened before the UI was built
                    for entry in console_log:
                        dpg.add_text(entry, color=LOG_COLOR)

            # ── dior tab ─────────────────────────────────────────────────────
            with dpg.tab(label="dior"):
                with dpg.child_window(
                    width=MATRIX_W + 6, height=MATRIX_H + 6,
                    border=False, no_scrollbar=True
                ):
                    dpg.add_drawlist(
                        width=MATRIX_W, height=MATRIX_H,
                        tag="matrix_drawlist"
                    )

        # ── Footer ───────────────────────────────────────
        dpg.add_spacer(height=4)
        dpg.add_separator()
        dpg.add_spacer(height=4)
        dpg.add_text("© 2026 Flag Browser | Made by imgui.cc", color=[120, 120, 120])

    dpg.set_primary_window("main_window", True)
    dpg.setup_dearpygui()
    dpg.configure_viewport(0, always_on_top=ALWAYS_ON_TOP)
    dpg.show_viewport()
    show_startup_popup()

    threading.Thread(target=global_key_listener, daemon=True).start()

    # Custom render loop — drives matrix animation at ~20 fps without a thread
    while dpg.is_dearpygui_running():
        now = time.time()
        if now - last_matrix_t >= 0.05:
            update_matrix()
            last_matrix_t = now
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
