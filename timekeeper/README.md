# TimeKeeper

A cross-platform desktop time-budget tracker built with Python.
Track break usage against a configurable budget, export session 
logs to CSV, and view KPI analytics in a live web dashboard.

## Screenshot
![TimeKeeper screenshot](assets/screenshot.png)

## Features
- Start/stop session timer with a single button
- Arc gauge showing budget consumed in real time
- Editable starting budget (click the value to change it)
- Session log with scrollable history
- CSV export with per-session and cumulative stats
- Live KPI dashboard (Flask) that refreshes automatically on session stop
- Fully resizable UI
- Cross-platform: Windows and macOS

## Requirements
Python 3.8 or newer. Install dependencies with:
    pip install -r requirements.txt

## Running from source
    python time_tracker.py

## Building a standalone executable
Windows:
    pyinstaller TimeKeeper.spec

macOS:
    pyinstaller TimeKeeper_mac.spec

## Tech stack
- tkinter — GUI
- Flask — dashboard web server
- pandas — CSV analytics
- PyInstaller — packaging
