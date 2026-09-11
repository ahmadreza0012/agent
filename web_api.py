#!/usr/bin/env python3
"""
Single Unified Dashboard Launcher
Launches the full Node.js dashboard (server.js) on Port 5000.
Ensures there is ONLY ONE dashboard running on port 5000.
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    port = os.environ.get("PORT", "5000")
    print(f"==================================================")
    print(f"🚀 Starting Single Unified Trading Dashboard on Port {port}")
    print(f"   URL: http://0.0.0.0:{port}")
    print(f"==================================================")

    env = dict(os.environ)
    env["PORT"] = port

    # Run the Node.js unified dashboard server
    server_js = os.path.join(BASE_DIR, "server.js")
    if os.path.exists(server_js):
        try:
            subprocess.run(["node", "server.js"], cwd=BASE_DIR, env=env)
        except KeyboardInterrupt:
            print("\nDashboard stopped by user.")
    else:
        print(f"Error: {server_js} not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
