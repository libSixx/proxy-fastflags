import json
import requests
import dearpygui.dearpygui as dpg
import urllib3
import keyboard
import time
import threading
from tkinter import Tk, filedialog
import pyperclip
import os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "config.json"
FLAGS_URL = "https://raw.githubusercontent.com/MaximumADHD/Roblox-Client-Tracker/refs/heads/roblox/FVariables.txt"
DEFAULT_JSON_PATH = ""

keybinds = {}
is_setting_keybind = False
last_keybind_time = 0

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        JSON_PATH = config.get("json_path", DEFAULT_JSON_PATH)
        ALWAYS_ON_TOP = config.get("always_on_top", False)
else:
    JSON_PATH = DEFAULT_JSON_PATH
    ALWAYS_ON_TOP = False
    with open(CONFIG_FILE, "w") as f:
        json.dump({"json_path": JSON_PATH, "always_on_top": ALWAYS_ON_TOP}, f)

def load_json():
    try:
        with open(JSON_PATH, "r") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data.setdefault("dczSettings", {})
    data.setdefault("disabledFlags", {})
    data.setdefault("keybinds", {})

    if "flagOrder" not in data:
        data["flagOrder"] = list(data["dczSettings"].keys()) + list(data["disabledFlags"].keys())

    return data, data["keybinds"]

def save_json(data):
    data["flagOrder"] = [flag for flag in data["flagOrder"] if flag in data["dczSettings"] or flag in data["disabledFlags"]]
    data["keybinds"] = keybinds
    with open(JSON_PATH, "w") as file:
        json.dump(data, file, indent=4)

def fetch_flags():
    response = requests.get(FLAGS_URL, verify=False)
    lines = response.text.split("\n")
    allowed_prefixes = ("DFInt", "DFFlag", "DFString")
    flags = []
    for line in lines:
        if line.startswith(("[C++]", "[Lua]")) and " " in line:
            flag_name = line.split(" ", 1)[1]
            if flag_name.startswith(allowed_prefixes):
                flags.append(flag_name)
    return flags

def clear_keybind(sender, app_data, flag):
    if flag in keybinds:
        del keybinds[flag]
    save_json(settings)
    dpg.configure_item(f"keybind_button_{flag}", label="Keybind: none")
    dpg.configure_item(f"clear_keybind_button_{flag}", show=False)

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
                if pressed_key in ["CTRL", "SHIFT"]:  
                    pressed_modifier = pressed_key
                    continue
                modifier = ""
                if keyboard.is_pressed("ctrl"):
                    modifier = "CTRL + "
                elif keyboard.is_pressed("shift"):
                    modifier = "SHIFT + "
                keybinds[flag] = f"{modifier}{pressed_key}"
                save_json(settings)
                dpg.configure_item(f"keybind_button_{flag}", label=f"Keybind: {modifier}{pressed_key}")
                dpg.configure_item(f"clear_keybind_button_{flag}", show=True)
                last_keybind_time = time.time()
                is_setting_keybind = False
                break
            elif event.event_type == keyboard.KEY_UP and pressed_modifier:
                keybinds[flag] = pressed_modifier
                save_json(settings)
                dpg.configure_item(f"keybind_button_{flag}", label=f"Keybind: {pressed_modifier}")
                dpg.configure_item(f"clear_keybind_button_{flag}", show=True)
                last_keybind_time = time.time()
                is_setting_keybind = False
                break
    threading.Thread(target=capture_key, daemon=True).start()

def global_key_listener():
    pressed_keys = set()
    while True:
        event = keyboard.read_event()
        if is_setting_keybind:
            continue
        if event.event_type == keyboard.KEY_DOWN:
            modifier = ""
            pressed_key = event.name.upper()
            if keyboard.is_pressed("ctrl"):
                modifier = "CTRL + "
            elif keyboard.is_pressed("shift"):
                modifier = "SHIFT + "
            full_keybind = f"{modifier}{pressed_key}"
            if full_keybind not in pressed_keys and pressed_key not in pressed_keys:
                pressed_keys.add(full_keybind)
                pressed_keys.add(pressed_key)

                for flag, key in keybinds.items():
                    if key == full_keybind or key == pressed_key:
                        if dpg.does_item_exist(f"enabled_checkbox_{flag}"):
                            current_state = dpg.get_value(f"enabled_checkbox_{flag}")
                            dpg.set_value(f"enabled_checkbox_{flag}", not current_state)
                            toggle_flag_visibility(None, None, flag)
        elif event.event_type == keyboard.KEY_UP:
            released_key = event.name.upper()
            modifier_key = f"CTRL + {released_key}" if "CTRL" in pressed_keys else f"SHIFT + {released_key}"
            pressed_keys.discard(released_key)
            pressed_keys.discard(modifier_key)

flags_list = fetch_flags()
settings, keybinds = load_json()
selected_flag = None

def save_flag(name, value):
    if name not in settings["flagOrder"]:
        settings["flagOrder"].append(name)
    
    if name in settings["disabledFlags"]:
        settings["disabledFlags"][name] = value
    else:
        settings["dczSettings"][name] = value
    
    save_json(settings)
    update_enabled_flags_list()

def remove_flag(sender, app_data, flag):
    if flag in settings["dczSettings"]:
        del settings["dczSettings"][flag]
    if flag in settings["disabledFlags"]:
        del settings["disabledFlags"][flag]
    if flag in settings["flagOrder"]:
        settings["flagOrder"].remove(flag)
    if flag in keybinds:
        del keybinds[flag]

    save_json(settings)
    update_enabled_flags_list()

def toggle_flag_visibility(sender, app_data, flag):
    if flag in settings["dczSettings"]:
        settings["disabledFlags"][flag] = settings["dczSettings"].pop(flag)
    else:
        settings["dczSettings"][flag] = settings["disabledFlags"].pop(flag)

    save_json(settings)
    update_enabled_flags_list()

def update_json_path(sender, app_data):
    global JSON_PATH, settings, keybinds
    JSON_PATH = app_data

    with open(CONFIG_FILE, "w") as f:
        json.dump({"json_path": JSON_PATH}, f)

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
            json.dump({"json_path": JSON_PATH}, f)

        settings, keybinds = load_json()
        update_enabled_flags_list()

def update_search(sender, app_data):
    search_query = app_data.lower()
    update_flag_list(search_query)

def select_flag(sender, app_data, flag):
    global selected_flag
    selected_flag = flag
    dpg.set_value("selected_flag_text", f"Selected Flag: {flag}")

def set_flag_value(sender, app_data):
    global selected_flag
    if selected_flag:
        new_value = dpg.get_value("flag_value_input")
        save_flag(selected_flag, new_value)
        dpg.set_value("flag_value_input", "")
        selected_flag = None
        dpg.set_value("selected_flag_text", "Selected Flag: None")
        if dpg.does_item_exist(f"display_value_{selected_flag}"):
            dpg.configure_item(f"display_value_{selected_flag}", default_value=f"{selected_flag}: {new_value}")

def update_flag_list(search_query=""):
    dpg.delete_item("available_flags_list", children_only=True)
    for flag in flags_list:
        if search_query in flag.lower():
            dpg.add_button(label=flag, parent="available_flags_list", callback=select_flag, user_data=flag)

def update_enabled_flags_list():
    existing_inputs = {}
    for flag in settings["flagOrder"]:
        if dpg.does_item_exist(f"edit_value_{flag}"):
            existing_inputs[flag] = dpg.get_value(f"edit_value_{flag}")
    dpg.delete_item("enabled_flags_list", children_only=True)
    settings["flagOrder"] = [flag for flag in settings["flagOrder"] if flag in settings["dczSettings"] or flag in settings["disabledFlags"]]
    for index, flag in enumerate(settings["flagOrder"]):
        is_enabled = flag in settings["dczSettings"]
        keybind_label = f"Keybind: {keybinds.get(flag, 'none')}"
        checkbox_tag = f"enabled_checkbox_{flag}"
        
        with dpg.group(parent="enabled_flags_list"):
            dpg.add_input_text(tag=f"display_value_{flag}", default_value=f"{flag}: {settings['dczSettings'].get(flag, settings['disabledFlags'].get(flag, ''))}", width=561, readonly=True)
            with dpg.group(horizontal=True):
                dpg.add_input_text(tag=f"edit_value_{flag}", width=400, hint="enter new value...")
                dpg.add_button(label="Update Value", callback=update_flag_value, user_data=flag)
            with dpg.group(horizontal=True):
                dpg.add_checkbox(label="Enabled", default_value=is_enabled, callback=toggle_flag_visibility, user_data=flag, tag=checkbox_tag)
                dpg.add_button(label="Remove", callback=remove_flag, user_data=flag)
                with dpg.group(horizontal=True):
                    dpg.add_button(label=keybind_label, callback=set_keybind, user_data=flag, tag=f"keybind_button_{flag}")
                    
                    x_button_visibility = flag in keybinds
                    dpg.add_button(label="X", callback=clear_keybind, user_data=flag, width=25, tag=f"clear_keybind_button_{flag}", show=x_button_visibility)
            if index < len(settings["flagOrder"]) - 1:
                dpg.add_spacer(height=10)
    for flag, value in existing_inputs.items():
        if dpg.does_item_exist(f"edit_value_{flag}"):
            dpg.set_value(f"edit_value_{flag}", value)

def toggle_always_on_top(sender, app_data):
    global ALWAYS_ON_TOP
    ALWAYS_ON_TOP = app_data
    dpg.configure_viewport(0, always_on_top=ALWAYS_ON_TOP)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"json_path": JSON_PATH, "always_on_top": ALWAYS_ON_TOP}, f)

def update_flag_value(sender, app_data, flag):
    new_value = dpg.get_value(f"edit_value_{flag}")
    if flag in settings["dczSettings"]:
        settings["dczSettings"][flag] = new_value
    elif flag in settings["disabledFlags"]:
        settings["disabledFlags"][flag] = new_value
    save_json(settings)
    dpg.set_value(f"edit_value_{flag}", "")
    dpg.configure_item(f"display_value_{flag}", default_value=f"{flag}: {new_value}")

def show_json_import_popup():
    if not dpg.does_item_exist("json_import_popup"):
        with dpg.window(label="Import JSON", modal=True, no_resize=True, no_close=True, no_collapse=True, tag="json_import_popup"):
            dpg.add_text("Paste JSON here:")
            dpg.add_input_text(multiline=True, width=400, height=250, tag="json_input_text")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Import", callback=import_json_from_input)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("json_import_popup"))
    else:
        dpg.show_item("json_import_popup")

def import_json_from_input(sender, app_data):
    json_content = dpg.get_value("json_input_text")
    try:
        data = json.loads(json_content)
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure.")
        invalid_flags = [key for key in data if key not in flags_list]
        if invalid_flags:
            raise ValueError(f"Invalid flags not found in Available Flags: {', '.join(invalid_flags)}")
        for key, value in data.items():
            if isinstance(value, dict):
                raise ValueError("Nested JSON is not allowed.")
            if not key.startswith(("DFFlag", "DFInt", "DFString")):
                raise ValueError(f"Invalid key: {key}")
        for key, value in data.items():
            if key in settings["disabledFlags"]:
                settings["disabledFlags"][key] = value
            elif key in settings["dczSettings"]:
                settings["dczSettings"][key] = value
            else:
                settings["dczSettings"][key] = value
            if key not in settings["flagOrder"]:
                settings["flagOrder"].append(key)
        save_json(settings)
        update_enabled_flags_list()
        dpg.set_value("json_feedback", "Import JSON: Successfully imported.")
        dpg.configure_item("json_feedback", color=[0, 255, 0])
        dpg.delete_item("json_import_popup")
    except (json.JSONDecodeError, ValueError) as e:
        dpg.set_value("json_feedback", f"Import JSON: {str(e)}")
        dpg.configure_item("json_feedback", color=[255, 0, 0])
    threading.Timer(5, lambda: dpg.set_value("json_feedback", "")).start()

def export_json(sender, app_data):
    export_data = {
        key: settings["dczSettings"].get(key, settings["disabledFlags"].get(key, ""))
        for key in settings["flagOrder"]
    }
    clipboard_content = json.dumps(export_data, indent=4)
    try:
        pyperclip.copy(clipboard_content)
        dpg.set_value("json_feedback", "Export JSON: Successfully copied to clipboard")
        dpg.configure_item("json_feedback", color=[0, 255, 0])
    except Exception as e:
        dpg.set_value("json_feedback", f"Export JSON: Failed to copy ({str(e)})")
        dpg.configure_item("json_feedback", color=[255, 0, 0])
    threading.Timer(5, lambda: dpg.set_value("json_feedback", "")).start()

def show_startup_popup():
    with dpg.window(
        label="lmao really...",
        modal=True,
        no_resize=True,
        no_close=True,
        no_collapse=True,
        tag="startup_popup",
        width=340,
        pos=[130, 300]
    ):
        dpg.add_spacer(height=4)
        dpg.add_text("how u gon leak something that doesnt work lol.")
        dpg.add_spacer(height=2)
        dpg.add_text("est. 2023", color=[160, 160, 160])
        dpg.add_spacer(height=8)
        dpg.add_button(
            label="ok bro my bad",
            width=-1,
            callback=lambda: dpg.delete_item("startup_popup")
        )
        dpg.add_spacer(height=4)

def main():
    dpg.create_context()
    dpg.create_viewport(title='Main', width=610, height=750, resizable=False)
    with dpg.window(label=' ', width=600, height=750, no_close=True, no_collapse=True, no_title_bar=True, no_move=True, no_resize=True, tag="main_window"):
        with dpg.tab_bar():
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
            with dpg.tab(label="Settings"):
                dpg.add_spacer(height=2.5)
                dpg.add_input_text(label="JSON Path", default_value=JSON_PATH, callback=update_json_path, readonly=True, tag="json_path_input")
                dpg.add_button(label="Select File", callback=select_json_file)
                dpg.add_spacer(height=5)
                dpg.add_separator()
                dpg.add_spacer(height=5)
                dpg.add_checkbox(label="AlwaysOnTop Enabled", default_value=ALWAYS_ON_TOP, callback=toggle_always_on_top, tag="always_on_top_checkbox")
                dpg.add_spacer(height=5)
                dpg.add_separator()
                dpg.add_spacer(height=5)
                dpg.add_button(label="Import JSON", callback=show_json_import_popup)
                dpg.add_spacer(height=2)
                dpg.add_button(label="Export JSON", callback=export_json)
                dpg.add_spacer(height=2)
                dpg.add_text("", tag="json_feedback")

        # Footer — visible on every tab
        dpg.add_spacer(height=4)
        dpg.add_separator()
        dpg.add_spacer(height=4)
        dpg.add_text(
            "© 2026 Flag Browser | Made by imgui.cc",
            color=[120, 120, 120]
        )

    dpg.set_primary_window("main_window", True)
    dpg.setup_dearpygui()
    dpg.configure_viewport(0, always_on_top=ALWAYS_ON_TOP)
    dpg.show_viewport()

    show_startup_popup()

    listener_thread = threading.Thread(target=global_key_listener, daemon=True)
    listener_thread.start()
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    main()
