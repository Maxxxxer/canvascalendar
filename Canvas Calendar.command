#!/bin/bash
cd "$(dirname "$0")"
python3 canvas_calendar.py &
disown
