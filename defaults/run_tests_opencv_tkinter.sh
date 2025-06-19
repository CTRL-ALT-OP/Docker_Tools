#!/bin/sh
# entrypoint: create the socket dir, start Xvfb, wait, then run pytest
\
    Xvfb :99 -screen 0 1024x768x24 -ac & \
    sleep 1 && \
    export DISPLAY=:99 && \
    python3.12 -m pytest -vv -s tests/ \
