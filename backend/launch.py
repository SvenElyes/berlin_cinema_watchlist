"""Launches the Flask backend in the background and shows it in a native
window. Closing the window stops the server and exits.
"""

import threading

import webview

from app import app


def _run_server():
    app.run(port=5001, use_reloader=False)


if __name__ == "__main__":
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    webview.create_window("Berlin Rerelease Finder", "http://127.0.0.1:5001")
    webview.start()
