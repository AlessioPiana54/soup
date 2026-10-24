# Built from the repository root (docker-compose: context ".", dockerfile
# soup-server/Dockerfile) so the image also gets soup-packages/. The
# layout /srv/soup-server + /srv/soup-packages mirrors the repository, so
# Settings finds the bundled packages at its default path.
FROM python:3.11.5-slim

WORKDIR /srv/soup-server

COPY soup-server/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY soup-server/ .
COPY soup-packages/ /srv/soup-packages/

# Packages installed at runtime (and their enabled/disabled state) live in
# a volume, so they survive a rebuild of the image.
ENV SOUP_INSTALLED_PACKAGES_DIR=/data/soup-packages
VOLUME /data/soup-packages

CMD ["python", "-u", "app.py"]
