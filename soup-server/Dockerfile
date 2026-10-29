# Built from the repository root (docker-compose: context ".", dockerfile
# soup-server/Dockerfile) so the image also gets soup-packages/. The
# layout /srv/soup-server + /srv/soup-packages mirrors the repository, so
# Settings finds the bundled packages at its default path.

# Frontend bundles of the packages: the @soup/sdk and app/dist/index.js of
# every package with an app/ part, served by /api/v3/packages/<n>/app/.
FROM node:24.22.0-alpine AS packages

WORKDIR /srv/soup-packages

COPY soup-packages/ .

RUN npm ci && npm run build:packages && rm -rf node_modules

FROM python:3.12.16-slim

WORKDIR /srv/soup-server

COPY soup-server/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# A binary incompatibility (e.g. numpy 2.x under pandas 2.1.1) fails the
# build here instead of the start of the packages.
RUN python -c "import numpy, pandas, neo4j, docker, waitress; print(numpy.__version__, pandas.__version__)"

COPY soup-server/ .
COPY --from=packages /srv/soup-packages/ /srv/soup-packages/

# Packages installed at runtime (and their enabled/disabled state) live in
# a volume, so they survive a rebuild of the image.
ENV SOUP_INSTALLED_PACKAGES_DIR=/data/soup-packages
VOLUME /data/soup-packages

# waitress (wsgi.py), one process with several threads: the engine keeps
# its state in memory. app.py (the Flask development server) is for local
# development only.
CMD ["python", "-u", "wsgi.py"]
