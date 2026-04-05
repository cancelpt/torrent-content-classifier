"""Module entrypoint for `python -m torrent_content_classifier`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
