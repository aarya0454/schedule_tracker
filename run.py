#!/usr/bin/env python3
"""
Startup script for the Daily Check-In App
"""
from app import app

if __name__ == '__main__':
    print("Starting Daily Check-In App...")
    print("Open your browser and go to: http://localhost:5002")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=5002) 