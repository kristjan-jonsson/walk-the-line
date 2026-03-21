FROM python:3.11-slim

# SDL2 headers/libs needed by pygame-ce at install time,
# and a virtual framebuffer so pygame can init without a real display.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsdl2-dev \
        libsdl2-image-dev \
        libsdl2-mixer-dev \
        libsdl2-ttf-dev \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt pytest

# Run tests, then build the web artefact.
# SDL_VIDEODRIVER=dummy lets pygame initialise without a display.
# The build output lands in build/web/ — mount a volume there to extract it:
#   podman run --rm -v ./build:/app/build walk-the-line
ENV SDL_VIDEODRIVER=dummy
ENV SDL_AUDIODRIVER=dummy

RUN python -m pytest tests/ -v

RUN python -m pygbag --build --width 960 --height 600 main.py
