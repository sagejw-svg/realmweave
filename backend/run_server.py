#!/usr/bin/env python3
"""Start the Realmweave WebSocket server (the authoritative world).

    pip install websockets
    python run_server.py

Then launch the Godot client (godot_client/) which connects to ws://127.0.0.1:8765.
Set "force_stub": true in config.json to run without Ollama/GPU.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realmweave.server import main

if __name__ == "__main__":
    main()
