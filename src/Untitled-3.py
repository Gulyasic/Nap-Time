import ctypes
import math
import os
import subprocess
import sys
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox

BG = '#0b0d14'
PANEL = '#141823'
FIELD = '#1d2331'
BORDER = '#2a3141'
TEXT = '#f5f5fa'
MUTED = '#929aaf'
ACCENT = '#b8f36b'
RED = '#ff8d91'
MAX_SECONDS = 315360000
ACTIONS = {'Вимкнення': '/s', 'Перезавантаження': '/r'}
SCRIPT_DIR = Path(__file__).resolve().parent
ASSET_DIR = (SCRIPT_DIR if getattr(sys, 'frozen', False) else SCRIPT_DIR.parent) / 'assets'
READY_MESSAGE = 'Обери тривалість і дію'


def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


def run_shutdown(*args):
    if sys.platform != 'win32':
        raise OSError('Ця дія доступна лише у Windows.')
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'shutdown.exe'
    subprocess.run(
        [str(executable), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=5,
    )


class App:
    def __init__(self, root):
        self.root = root
        self.deadline = None
        self.after_id = None
        self.entries = []
        self.presets = []
        self.action_buttons = []
        self.action = next(iter(ACTIONS))
        root.title('Тихий час — таймер')
        root.configure(bg=BG)
        root.geometry('440x650')
        root.minsize(420, 620)
        try:
            root.iconbitmap(str(ASSET_DIR / 'timer.ico'))
        except tk.TclError:
            try:
                self.icon = tk.PhotoImage(file=str(ASSET_DIR / 'timer.png'))
                root.iconphoto(True, self.icon)
            except tk.TclError:
                pass
        root.after_idle(self.style_titlebar)

        page = tk.Frame(root, bg=BG)
        page.pack(fill='both', expand=True, padx=24, pady=(18, 16))
        self.label(page, 'Тихий час', 23, TEXT, True, family='Segoe UI Semibold').pack(pady=(0, 2))
        self.label(page, 'Таймер для твого комп’ютера', 10, MUTED).pack()

        hero = tk.Frame(page, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill='x', pady=(15, 14))
        hero_top = tk.Frame(hero, bg=PANEL)
        hero_top.pack(fill='x', padx=16, pady=(12, 0))
        self.label(hero_top, 'ЗАЛИШИЛОСЯ', 9, MUTED, True, bg=PANEL).pack(side='left')
        self.status = self.label(hero_top, '●  ГОТОВО', 9, ACCENT, True, bg=PANEL)
        self.status.pack(side='right')
        self.timer = self.label(hero, '00:00:00', 36, TEXT, True, bg=PANEL, family='Consolas')
        self.timer.pack(pady=(5, 0))
        self.finish = self.label(hero, READY_MESSAGE, 10, MUTED, bg=PANEL)
        self.finish.pack(pady=(0, 12))

        heading = tk.Frame(page, bg=BG)
        heading.pack(fill='x')
        self.label(heading, 'Тривалість', 12, TEXT, True).pack(side='left')
        inputs = tk.Frame(page, bg=BG)
        inputs.pack(fill='x', pady=(9, 9))
        for col, title in enumerate(('год', 'хв', 'сек')):
            inputs.grid_columnconfigure(col, weight=1, uniform='time')
            box = tk.Frame(inputs, bg=FIELD, highlightbackground=BORDER, highlightthickness=1)
            box.grid(row=0, column=col, sticky='ew', padx=(0 if col == 0 else 5, 0 if col == 2 else 5))
            entry = tk.Entry(box, width=4, justify='center', font=('Segoe UI', 17, 'bold'),
                             bg=FIELD, fg=TEXT, insertbackground=ACCENT, relief='flat',
                             disabledbackground=FIELD, disabledforeground=MUTED)
            entry.pack(side='left', fill='x', expand=True, padx=(8, 0), pady=9)
            self.label(box, title, 9, MUTED, bg=FIELD).pack(side='right', padx=(0, 12))
            self.entries.append(entry)
            entry.bind('<MouseWheel>', lambda event, field=entry, index=col: self.scroll_time(event, field, index))
        self.set_time(0, 30, 0)
        row = tk.Frame(page, bg=BG)
        row.pack(fill='x')
        self.label(row, 'Швидко:', 9, MUTED).pack(side='left', padx=(0, 7))
        for title, minutes in (('15 хв', 15), ('30 хв', 30), ('1 год', 60)):
            button = self.button(row, title, lambda m=minutes: self.set_time(m // 60, m % 60, 0), FIELD, TEXT, 9, 5)
            button.pack(side='left', padx=(0, 6))
            self.presets.append(button)

        self.label(page, 'Що зробити?', 12, TEXT, True).pack(anchor='w', pady=(13, 7))
        actions = tk.Frame(page, bg=BG)
        actions.pack(fill='x')
        for col, name in enumerate(ACTIONS):
            actions.grid_columnconfigure(col, weight=1, uniform='actions')
            button = self.button(actions, name, lambda value=name: self.select_action(value), FIELD, TEXT, 10, 10)
            button.grid(row=0, column=col, sticky='nsew', padx=(0, 5) if col == 0 else (5, 0))
            self.action_buttons.append(button)
        self.update_actions()

        controls = tk.Frame(page, bg=BG)
        controls.pack(fill='x', pady=(14, 0))
        self.start = self.button(controls, 'Запустити таймер  →', self.start_timer, ACCENT, '#15200b', 11, 9)
        self.start.pack(fill='x')
        self.cancel = self.button(controls, 'Скасувати дію', self.cancel_timer, FIELD, TEXT, 11, 9)
        self.cancel.pack(fill='x', pady=(7, 0))
        self.set_running(False)

    def style_titlebar(self):
        if sys.platform != 'win32':
            return
        try:
            get_parent = ctypes.windll.user32.GetParent
            get_parent.argtypes = (ctypes.c_void_p,)
            get_parent.restype = ctypes.c_void_p
            hwnd = ctypes.c_void_p(get_parent(self.root.winfo_id()))
            dark = ctypes.c_int(1)
            color = ctypes.c_int(0x140d0b)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
        except (AttributeError, OSError):
            pass

    @staticmethod
    def label(parent, text, size, color, bold=False, bg=BG, family='Segoe UI', **kwargs):
        return tk.Label(parent, text=text, font=(family, size, 'bold' if bold else 'normal'), fg=color, bg=bg, **kwargs)

    @staticmethod
    def button(parent, text, command, bg, fg, size=10, pady=8):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=BORDER, activeforeground=TEXT,
                         disabledforeground=MUTED, font=('Segoe UI', size, 'bold'),
                         relief='flat', bd=0, cursor='hand2', padx=12, pady=pady)

    def set_time(self, hours, minutes, seconds):
        for entry, value in zip(self.entries, (hours, minutes, seconds)):
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

    def scroll_time(self, event, entry, index):
        if str(entry['state']) == 'disabled' or not event.delta:
            return 'break'
        try:
            value = int(entry.get() or '0')
        except ValueError:
            value = 0
        maximum = MAX_SECONDS // 3600 if index == 0 else 59
        value = max(0, min(maximum, value + (1 if event.delta > 0 else -1)))
        entry.delete(0, tk.END)
        entry.insert(0, str(value))
        return 'break'

    def select_action(self, action):
        self.action = action
        self.update_actions()

    def update_actions(self):
        for button, value in zip(self.action_buttons, ACTIONS):
            selected = self.action == value
            button.config(bg='#303e2a' if selected else FIELD, fg=ACCENT if selected else MUTED)

    def set_running(self, running):
        for widget in [*self.entries, *self.presets, *self.action_buttons, self.start]:
            widget.config(state='disabled' if running else 'normal')

    def request_shutdown(self, *args, failure_status, failure_message):
        try:
            run_shutdown(*args)
        except subprocess.CalledProcessError as exc:
            detail = f'{failure_message}\n\nКод Windows: {exc.returncode}'
        except subprocess.TimeoutExpired:
            detail = 'Windows не відповіла вчасно. Стан запланованої дії невідомий.'
        except OSError as exc:
            detail = str(exc)
        else:
            return True
        self.status.config(text=failure_status, fg=RED)
        messagebox.showerror('Помилка Windows', detail, parent=self.root)
        return False

    def start_timer(self):
        try:
            values = [int(entry.get() or '0') for entry in self.entries]
            if min(values) < 0 or values[1] > 59 or values[2] > 59:
                raise ValueError
            total = values[0] * 3600 + values[1] * 60 + values[2]
            if not 0 < total <= MAX_SECONDS:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                'Невірний час',
                'Введи невід’ємні цілі числа. Хвилини та секунди — від 0 до 59, '
                'загальний час — від 1 секунди до 3650 днів.',
                parent=self.root,
            )
            return
        if not self.request_shutdown(
            ACTIONS[self.action], '/t', str(total),
            failure_status='●  ПОМИЛКА',
            failure_message='Не вдалося запланувати дію.',
        ):
            return
        self.deadline = time.monotonic() + total
        finish_time = datetime.now() + timedelta(seconds=total)
        self.finish.config(text=f'{self.action}  ·  {finish_time:%d.%m.%Y} о {finish_time:%H:%M:%S}')
        self.status.config(text='●  ПРАЦЮЄ', fg=ACCENT)
        self.set_running(True)
        self.tick()

    def tick(self):
        remaining = max(0, math.ceil(self.deadline - time.monotonic()))
        self.timer.config(text=format_time(remaining))
        if remaining:
            self.after_id = self.root.after(250, self.tick)
        else:
            self.after_id = None
            self.deadline = None
            self.set_running(False)
            self.status.config(text='●  ЧАС ВИЙШОВ', fg=RED)

    def cancel_timer(self):
        if not self.request_shutdown(
            '/a',
            failure_status='●  НЕ СКАСОВАНО',
            failure_message='Windows не підтвердила скасування запланованої дії.',
        ):
            return
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.deadline = None
        self.timer.config(text='00:00:00')
        self.finish.config(text=READY_MESSAGE)
        self.status.config(text='●  СКАСОВАНО', fg=ACCENT)
        self.set_running(False)


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
