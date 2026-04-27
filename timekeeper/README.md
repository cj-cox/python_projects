# TimeKeeper

A cross-platform desktop time-budget tracker built with Python.
Track break usage against a configurable budget, export session 
logs to CSV, and view KPI analytics in a live web dashboard.

## Background

I wanted to test the abilities of AI to aid in the development of a desktop application. 
TimeKeeper is the result of that experiment. AI was crucial in the overall design of the UI and the necessary code to ensure its proper functionality. 
After creating TimeKeeper, I performed basic data analysis on the resulting time information contained in the CSV logs. 
During my analysis, I realized it would be beneficial for the user to have the ability to quickly review their usage history and trends. 
I then utilized AI to assist with incorporating the Python script I created for analysis within TimeKeeper. 
The Dashboard button was then added to the interface. At this time, I then edited the resulting HTML file to acheive a more visualy appealing view of the Dashboard.  

## Screenshots

### TimeKeeper Windows Screenshot
<img src="https://github.com/cj-cox/python_projects/blob/main/timekeeper/images/win_image_01.png" alt="TimeKeeper Windows Screenshot" width="900">

### TimeKeeper macOS Screenshot
<img src="https://github.com/cj-cox/python_projects/blob/main/timekeeper/images/mac_image_01.png" alt="TimeKeeper macOS Screenshot" width="900">

### TimeKeeper Dashboard Screenshot
<img src="https://github.com/cj-cox/python_projects/blob/main/timekeeper/images/dash_image_01.png" alt="TimeKeeper Dashboard Screenshot" width="900">

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
Python 3.8 or newer
Dependencies:
* Flask
* pandas
* pyinstaller

## Running from source
    python time_tracker.py

## Building a standalone executable
Windows:
    pyinstaller TimeKeeper.spec

macOS:
    pyinstaller TimeKeeper_mac.spec

## Technology used
- tkinter — GUI
- Flask — dashboard web server
- pandas — CSV analytics
- PyInstaller — packaging
