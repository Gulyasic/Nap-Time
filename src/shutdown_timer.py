import ctypes
import math
import os
import subprocess
import sys
import time
import tkinter as tk
from datetime import datetime, timedelta
from datetime import time as clock_time
from pathlib import Path
from tkinter import messagebox

BG = '#0b0d14'
PANEL = '#141823'
FIELD = '#1d2331'
BORDER = '#2a3141'
TEXT = '#f5f5fa'
MUTED = '#929aaf'
ACCENT = '#b8f36b'
BUTTON_TEXT = '#15200b'
ORANGE = '#ffae5c'
RED = '#ff8d91'
MAX_SECONDS = 315360000
ACTIONS = {'Вимкнення': '/s', 'Перезавантаження': '/r'}
SCRIPT_DIR = Path(__file__).resolve().parent
ASSET_DIR = (SCRIPT_DIR if getattr(sys, 'frozen', False) else SCRIPT_DIR.parent) / 'assets'
READY_MESSAGE = 'Обери час і дію'
START_TEXT = 'Запустити таймер  →'
TIME_MODES = {'Через': False, 'О конкретній годині': True}


def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


def next_clock_time(now, hour, minute, selected_date=None):
    target = datetime.combine(selected_date or now.date(), clock_time(hour, minute))
    if selected_date is None and target <= now:
        target += timedelta(days=1)
    return datetime.fromtimestamp(target.timestamp())


def duration_seconds(hours, minutes, seconds):
    total = hours * 3600 + minutes * 60 + seconds
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError
    if not 0 < total <= MAX_SECONDS:
        raise ValueError
    return total


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


class ShutdownTimer:
    def __init__(self, root):
        self.root = root
        self.deadline = None
        self.paused_seconds = None
        self.after_id = None
        self.entries = []
        self.mode_buttons = []
        self.presets = []
        self.action_buttons = []
        self.clock_mode = False
        self.clock_date = None
        self.time_values = {False: ('0', '30', '0'), True: ('23', '30', '')}
        self.action = next(iter(ACTIONS))
        root.title('Тихий час — таймер')
        root.configure(bg=BG)
        root.geometry('440x650')
        root.minsize(420, 620)
        try:
            self.icon = tk.PhotoImage(master=root, file=str(ASSET_DIR / 'timer.png'))
        except tk.TclError:
            self.icon = None
        root.bind('<Map>', self.style_window)

        page = tk.Frame(root, bg=BG)
        page.pack(fill='both', expand=True, padx=24, pady=(18, 16))
        self.label(page, 'Тихий час', 23, TEXT, True, family='Segoe UI Semibold').pack(pady=(0, 2))
        self.build_countdown(page)
        self.build_time_inputs(page)
        self.build_controls(page)
        self.set_time(*self.time_values[self.clock_mode])
        self.update_controls()

    def build_countdown(self, page):
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

    def build_time_inputs(self, page):
        modes = tk.Frame(page, bg=BG)
        modes.pack(fill='x')
        for mode_label, clock_mode in TIME_MODES.items():
            button = self.button(modes, mode_label, lambda mode=clock_mode: self.select_mode(mode), FIELD, TEXT)
            button.pack(side='left', padx=(0, 6))
            self.mode_buttons.append(button)
        self.update_selection(self.mode_buttons, TIME_MODES.values(), self.clock_mode)

        self.time_inputs = tk.Frame(page, bg=BG)
        self.time_inputs.pack(fill='x', pady=9)
        for col, title in enumerate(('год', 'хв', 'сек')):
            self.time_inputs.grid_columnconfigure(col, weight=1, uniform='time')
            box = tk.Frame(self.time_inputs, bg=FIELD, highlightbackground=BORDER, highlightthickness=1)
            box.grid(row=0, column=col, sticky='ew', padx=(0 if col == 0 else 5, 0 if col == 2 else 5))
            entry = tk.Entry(box, width=4, justify='center', font=('Segoe UI', 17, 'bold'),
                             bg=FIELD, fg=TEXT, insertbackground=ACCENT, relief='flat',
                             disabledbackground=FIELD, disabledforeground=MUTED)
            entry.pack(side='left', fill='x', expand=True, padx=(8, 0), pady=9)
            self.label(box, title, 9, MUTED, bg=FIELD).pack(side='right', padx=(0, 12))
            self.entries.append(entry)
            entry.bind('<MouseWheel>', lambda event, field=entry, index=col: self.scroll_time(event, field, index))
            entry.bind('<KeyRelease>', lambda event: self.update_preview())
            if title == 'сек':
                self.seconds_box = box

        self.preset_row = tk.Frame(page, bg=BG)
        self.preset_row.pack(fill='x')
        for title, minutes in (('15 хв', 15), ('30 хв', 30), ('1 год', 60)):
            button = self.button(self.preset_row, title, lambda m=minutes: self.set_time(m // 60, m % 60, 0), FIELD, TEXT, 9, 5)
            button.pack(side='left', padx=(0, 6))
            self.presets.append(button)

    def build_controls(self, page):
        self.label(page, 'Що зробити?', 12, TEXT, True).pack(anchor='w', pady=(13, 7))
        actions = tk.Frame(page, bg=BG)
        actions.pack(fill='x')
        for col, name in enumerate(ACTIONS):
            actions.grid_columnconfigure(col, weight=1, uniform='actions')
            button = self.button(actions, name, lambda value=name: self.select_action(value), FIELD, TEXT, 10, 10)
            button.grid(row=0, column=col, sticky='nsew', padx=(0, 5) if col == 0 else (5, 0))
            self.action_buttons.append(button)
        self.update_selection(self.action_buttons, ACTIONS, self.action)

        controls = tk.Frame(page, bg=BG)
        controls.pack(fill='x', pady=(14, 0))
        self.start = self.button(controls, START_TEXT, self.toggle_timer, ACCENT, BUTTON_TEXT, 11, 9)
        self.start.pack(fill='x')
        self.cancel = self.button(controls, 'Скасувати', self.cancel_timer, FIELD, TEXT, 11, 9)
        self.cancel.pack(fill='x', pady=(7, 0))

    def style_window(self, event):
        if event.widget is not self.root:
            return
        if self.icon is not None:
            self.root.iconphoto(True, self.icon)
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
        self.update_preview()

    def select_mode(self, clock_mode):
        if self.clock_mode == clock_mode:
            return
        self.time_values[self.clock_mode] = tuple(entry.get() for entry in self.entries)
        self.clock_mode = clock_mode
        self.update_selection(self.mode_buttons, TIME_MODES.values(), clock_mode)
        if clock_mode:
            self.seconds_box.grid_remove()
            self.time_inputs.grid_columnconfigure(2, weight=0, uniform='')
            self.preset_row.pack_forget()
        else:
            self.seconds_box.grid()
            self.time_inputs.grid_columnconfigure(2, weight=1, uniform='time')
            self.preset_row.pack(fill='x', after=self.time_inputs)
            self.finish.config(text=READY_MESSAGE)
        self.set_time(*self.time_values[clock_mode])

    def clock_target(self, now):
        hour, minute = (int(entry.get()) for entry in self.entries[:2])
        return next_clock_time(now, hour, minute, self.clock_date)

    def update_preview(self):
        if not self.clock_mode or self.deadline is not None or self.paused_seconds is not None:
            return
        try:
            target = self.clock_target(datetime.now())
        except ValueError:
            self.finish.config(text='Введи годину й хвилини')
        else:
            self.finish.config(text=f'{self.action}  ·  {target:%d.%m.%Y} о {target:%H:%M}')

    def scroll_time(self, event, entry, index):
        if str(entry['state']) == 'disabled' or not event.delta:
            return 'break'
        try:
            value = int(entry.get() or '0')
        except ValueError:
            value = 0
        direction = 1 if event.delta > 0 else -1
        if self.clock_mode and index == 0:
            previous_hour = max(0, min(23, value))
            days, hour = divmod(previous_hour + direction, 24)
            if days:
                try:
                    minute = int(self.entries[1].get())
                except ValueError:
                    minute = 0
                selected_date = self.clock_date or next_clock_time(
                    datetime.now(), previous_hour, max(0, min(59, minute)),
                ).date()
                self.clock_date = selected_date + timedelta(days=days)
            value = f'{hour:02}'
        else:
            maximum = MAX_SECONDS // 3600 if index == 0 else 59
            value = str(max(0, min(maximum, value + direction)))
        entry.delete(0, tk.END)
        entry.insert(0, value)
        self.update_preview()
        return 'break'

    def select_action(self, action):
        self.action = action
        self.update_selection(self.action_buttons, ACTIONS, self.action)
        self.update_preview()

    @staticmethod
    def update_selection(buttons, values, current):
        for button, value in zip(buttons, values):
            selected = current == value
            button.config(bg='#303e2a' if selected else FIELD, fg=ACCENT if selected else MUTED)

    def update_controls(self):
        running = self.deadline is not None
        paused = self.paused_seconds is not None
        state = 'disabled' if running or paused else 'normal'
        for widget in [*self.entries, *self.mode_buttons, *self.presets, *self.action_buttons]:
            widget.config(state=state)
        if running:
            text, color = 'Пауза', ORANGE
        elif paused:
            text, color = 'Продовжити', ACCENT
        else:
            text, color = START_TEXT, ACCENT
        self.start.config(text=text, bg=color, activebackground=color, activeforeground=BUTTON_TEXT)
        self.cancel.config(state='normal' if running or paused else 'disabled')

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

    def toggle_timer(self):
        if self.deadline is not None:
            self.pause_timer()
        elif self.paused_seconds is not None:
            self.schedule_timer(self.paused_seconds)
        else:
            self.start_timer()

    def start_timer(self):
        finish_time = None
        try:
            if self.clock_mode:
                finish_time = self.clock_target(datetime.now())
            else:
                hours, minutes, seconds = (int(entry.get() or '0') for entry in self.entries)
                total = duration_seconds(hours, minutes, seconds)
        except ValueError:
            if self.clock_mode:
                detail = 'Введи годину від 0 до 23 і хвилини від 0 до 59.'
            else:
                detail = (
                    'Введи невід’ємні цілі числа. Хвилини та секунди — від 0 до 59, '
                    'загальний час — від 1 секунди до 3650 днів.'
                )
            messagebox.showerror('Невірний час', detail, parent=self.root)
            return
        if finish_time is not None:
            target_timestamp = finish_time.timestamp()
            if target_timestamp <= time.time():
                self.update_preview()
                messagebox.showerror('Час минув', 'Обери майбутню дату й час.', parent=self.root)
                return
            if not messagebox.askokcancel(
                'Підтвердження дії',
                f'{self.action} заплановано на {finish_time:%d.%m.%Y} о {finish_time:%H:%M}. Запустити таймер?',
                parent=self.root,
            ):
                return
            total = math.ceil(target_timestamp - time.time())
            if total <= 0:
                self.update_preview()
                messagebox.showerror('Час минув', 'Обери майбутню дату й час.', parent=self.root)
                return
            if total > MAX_SECONDS:
                messagebox.showerror('Невірний час', 'Обери дату в межах 3650 днів.', parent=self.root)
                return
        self.schedule_timer(total, finish_time)

    def schedule_timer(self, total, finish_time=None):
        if not self.request_shutdown(
            ACTIONS[self.action], '/t', str(total),
            failure_status='●  ПОМИЛКА',
            failure_message='Не вдалося запланувати дію.',
        ):
            return
        self.deadline = time.monotonic() + total
        self.paused_seconds = None
        if finish_time is None:
            finish_time = datetime.now() + timedelta(seconds=total)
        self.finish.config(text=f'{self.action}  ·  {finish_time:%d.%m.%Y} о {finish_time:%H:%M:%S}')
        self.status.config(text='●  ПРАЦЮЄ', fg=ACCENT)
        self.update_controls()
        self.tick()

    def tick(self):
        remaining = max(0, math.ceil(self.deadline - time.monotonic()))
        self.timer.config(text=format_time(remaining))
        if remaining:
            self.after_id = self.root.after(250, self.tick)
        else:
            self.after_id = None
            self.deadline = None
            self.update_controls()
            self.status.config(text='●  ЧАС ВИЙШОВ', fg=RED)

    def pause_timer(self):
        remaining = math.ceil(self.deadline - time.monotonic())
        if remaining <= 0 or not self.request_shutdown(
            '/a',
            failure_status='●  ПАУЗА НЕ ВДАЛАСЯ',
            failure_message='Windows не підтвердила зупинку запланованої дії.',
        ):
            return
        self.stop_countdown()
        self.paused_seconds = remaining
        self.timer.config(text=format_time(remaining))
        self.finish.config(text='Відлік призупинено')
        self.status.config(text='●  ПАУЗА', fg=ORANGE)
        self.update_controls()

    def stop_countdown(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.deadline = None

    def cancel_timer(self):
        if self.deadline is None and self.paused_seconds is None:
            return
        if self.paused_seconds is None and not self.request_shutdown(
            '/a',
            failure_status='●  НЕ СКАСОВАНО',
            failure_message='Windows не підтвердила скасування запланованої дії.',
        ):
            return
        self.stop_countdown()
        self.paused_seconds = None
        self.timer.config(text='00:00:00')
        self.finish.config(text=READY_MESSAGE)
        self.update_preview()
        self.status.config(text='●  СКАСОВАНО', fg=ACCENT)
        self.update_controls()


if __name__ == '__main__':
    root = tk.Tk()
    ShutdownTimer(root)
    root.mainloop()
