import json
import requests
import dearpygui.dearpygui as dpg
import urllib3
import keyboard
import time
import threading
import random
import subprocess
import sys
from tkinter import Tk, filedialog
import pyperclip
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "config.json"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "console.log")
FLAGS_URL = "https://raw.githubusercontent.com/MaximumADHD/Roblox-Client-Tracker/refs/heads/roblox/FVariables.txt"
DEFAULT_JSON_PATH = "flags.json"

keybinds = {}
is_setting_keybind = False
last_keybind_time = 0


# ---------------- FILE SETUP ---------------- #

def ensure_required_files():
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("=== Flag Browser Console Log ===\n")

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "json_path": DEFAULT_JSON_PATH,
                "always_on_top": False
            }, f, indent=4)

    if not os.path.exists(DEFAULT_JSON_PATH):
        with open(DEFAULT_JSON_PATH, "w") as f:
            json.dump({
                "dczSettings": {},
                "disabledFlags": {},
                "keybinds": {},
                "flagOrder": []
            }, f, indent=4)


def log(message):
    timestamp = time.strftime("[%H:%M:%S]")
    line = f"{timestamp} {message}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    if dpg.does_item_exist("console_output"):
        current = dpg.get_value("console_output")
        dpg.set_value("console_output", current + line + "\n")


ensure_required_files()


# ---------------- CONFIG ---------------- #

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

JSON_PATH = config.get("json_path", DEFAULT_JSON_PATH)
ALWAYS_ON_TOP = config.get("always_on_top", False)


def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "json_path": JSON_PATH,
            "always_on_top": ALWAYS_ON_TOP
        }, f, indent=4)


# ---------------- JSON ---------------- #

def load_json():
    try:
        with open(JSON_PATH, "r") as file:
            data = json.load(file)
    except:
        data = {}

    data.setdefault("dczSettings", {})
    data.setdefault("disabledFlags", {})
    data.setdefault("keybinds", {})
    data.setdefault("flagOrder", [])

    return data, data["keybinds"]


def save_json(data):
    data["keybinds"] = keybinds
    with open(JSON_PATH, "w") as file:
        json.dump(data, file, indent=4)


# ---------------- FLAGS ---------------- #

def fetch_flags():
    try:
        response = requests.get(FLAGS_URL, verify=False, timeout=10)
        lines = response.text.split("\n")

        allowed_prefixes = ("FInt", "FFlag", "FString", "DFInt", "DFFlag", "DFString")
        flags = []

        for line in lines:
            if line.startswith(("[C++]", "[Lua]")) and " " in line:
                flag_name = line.split(" ", 1)[1]
                if flag_name.startswith(allowed_prefixes):
                    flags.append(flag_name)

        log(f"Fetched {len(flags)} flags")
        return flags

    except Exception as e:
        log(f"Flag fetch failed: {e}")
        return []


flags_list = fetch_flags()
settings, keybinds = load_json()
selected_flag = None


# ---------------- FLAG MANAGEMENT ---------------- #

def save_flag(name, value):
    if name not in settings["flagOrder"]:
        settings["flagOrder"].append(name)

    settings["dczSettings"][name] = value
    save_json(settings)
    update_enabled_flags_list()
    log(f"Saved flag {name}")


def remove_flag(sender, app_data, flag):
    settings["dczSettings"].pop(flag, None)
    settings["disabledFlags"].pop(flag, None)

    if flag in settings["flagOrder"]:
        settings["flagOrder"].remove(flag)

    save_json(settings)
    update_enabled_flags_list()
    log(f"Removed flag {flag}")


def toggle_flag_visibility(sender, app_data, flag):
    if flag in settings["dczSettings"]:
        settings["disabledFlags"][flag] = settings["dczSettings"].pop(flag)
    else:
        settings["dczSettings"][flag] = settings["disabledFlags"].pop(flag)

    save_json(settings)
    update_enabled_flags_list()
    log(f"Toggled {flag}")


# ---------------- SEARCH ---------------- #

def update_search(sender, app_data):
    update_flag_list(app_data.lower())


def update_flag_list(search_query=""):
    dpg.delete_item("available_flags_list", children_only=True)

    for flag in flags_list:
        if search_query in flag.lower():
            dpg.add_button(
                label=flag,
                parent="available_flags_list",
                callback=select_flag,
                user_data=flag
            )


def select_flag(sender, app_data, flag):
    global selected_flag
    selected_flag = flag
    dpg.set_value("selected_flag_text", f"Selected Flag: {flag}")


def set_flag_value(sender, app_data):
    global selected_flag

    if selected_flag:
        value = dpg.get_value("flag_value_input")
        save_flag(selected_flag, value)
        dpg.set_value("flag_value_input", "")
        dpg.set_value("selected_flag_text", "Selected Flag: None")
        selected_flag = None


# ---------------- ENABLED FLAGS UI ---------------- #

def update_enabled_flags_list():
    dpg.delete_item("enabled_flags_list", children_only=True)

    for flag in settings["flagOrder"]:
        value = settings["dczSettings"].get(
            flag,
            settings["disabledFlags"].get(flag, "")
        )

        with dpg.group(parent="enabled_flags_list"):
            dpg.add_input_text(
                default_value=f"{flag}: {value}",
                readonly=True,
                width=560
            )

            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    label="Enabled",
                    default_value=flag in settings["dczSettings"],
                    callback=toggle_flag_visibility,
                    user_data=flag
                )
                dpg.add_button(
                    label="Remove",
                    callback=remove_flag,
                    user_data=flag
                )


# ---------------- SETTINGS ---------------- #

def toggle_always_on_top(sender, app_data):
    global ALWAYS_ON_TOP
    ALWAYS_ON_TOP = app_data
    dpg.configure_viewport(0, always_on_top=ALWAYS_ON_TOP)
    save_config()
    log(f"AlwaysOnTop set to {ALWAYS_ON_TOP}")


def select_json_file():
    global JSON_PATH

    root = Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json")]
    )

    if file_path:
        JSON_PATH = file_path
        dpg.set_value("json_path_input", JSON_PATH)
        save_config()
        log(f"Selected JSON: {file_path}")


# ---------------- CONSOLE ---------------- #

def load_console():
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            dpg.set_value("console_output", f.read())
    except:
        pass


def clear_logs():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== Console Cleared ===\n")

    load_console()


# ---------------- DIOR TAB ---------------- #

def launch_dior():
    code = '''
import curses, random, time

CHARS="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*+-=/<>"

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    h,w=stdscr.getmaxyx()
    drops=[random.randint(0,h) for _ in range(w)]

    while True:
        stdscr.clear()

        for x in range(w):
            y=drops[x]
            if 0<=y<h:
                try:
                    stdscr.addstr(y,x,random.choice(CHARS))
                except:
                    pass

            drops[x]+=1
            if drops[x]>h:
                drops[x]=0

        stdscr.refresh()
        time.sleep(0.03)

        if stdscr.getch()!=-1:
            break

curses.wrapper(main)
'''
    subprocess.Popen([sys.executable, "-c", code])
    log("Launched Dior visual")


# ---------------- UI ---------------- #

def main():
    dpg.create_context()
    dpg.create_viewport(title="Main", width=620, height=780, resizable=False)

    with dpg.window(
        label=" ",
        tag="main_window",
        no_title_bar=True,
        no_resize=True,
        no_move=True
    ):
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
                with dpg.child_window(height=280, tag="enabled_flags_list"):
                    update_enabled_flags_list()

            with dpg.tab(label="Settings"):
                dpg.add_input_text(
                    label="JSON Path",
                    default_value=JSON_PATH,
                    readonly=True,
                    tag="json_path_input"
                )
                dpg.add_button(label="Select File", callback=select_json_file)
                dpg.add_checkbox(
                    label="Always On Top",
                    default_value=ALWAYS_ON_TOP,
                    callback=toggle_always_on_top
                )

                dpg.add_separator()
                dpg.add_text("Console Log")
                dpg.add_input_text(
                    multiline=True,
                    readonly=True,
                    height=250,
                    width=580,
                    tag="console_output"
                )
                dpg.add_button(label="Refresh Logs", callback=lambda: load_console())

            with dpg.tab(label="Dior"):
                dpg.add_text("Fun Utilities")
                dpg.add_button(label="Launch Visuals", callback=launch_dior)
                dpg.add_button(label="Clear Logs", callback=lambda: clear_logs())
                dpg.add_spacer(height=10)
                dpg.add_text("build: experimental pink")

        dpg.add_separator()
        dpg.add_text(
            "© 2026 Flag Browser | Made by imgui.cc",
            color=[120, 120, 120]
        )

    dpg.set_primary_window("main_window", True)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    load_console()

    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
