"""Disposable isolated store for the real-browser suite."""

import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

from athleteos.server import Handler, Store


def main():
    with tempfile.TemporaryDirectory(prefix="athleteos-browser-") as directory:
        Handler.store = Store(Path(directory) / "state.json")
        server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
