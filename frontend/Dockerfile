# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Frontend image — Vite build on Node 20, served by nginx on port 8080.
# Build context is the REPOSITORY ROOT (see docker-compose.yml / render.yaml).
# The API base URL is baked into the JS bundle at BUILD time; there are no
# runtime secrets in this image.
# ---------------------------------------------------------------------------

FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first so this layer is cached independently of source.
COPY frontend/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./

# Render translates service env vars into Docker build args automatically;
# docker-compose passes this explicitly. The default only matters for a bare
# `docker build` with no args.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build


FROM nginx:1.27-alpine AS runtime

# Run nginx as the unprivileged `nginx` user. Writable paths live under /app,
# NOT /tmp: Render mounts an empty tmpfs at /tmp, which deletes anything we
# create there at build time and makes nginx fail with "mkdir() ... No such
# file or directory" on startup.
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i -e 's|/var/cache/nginx|/app/nginx-tmp|g' \
            -e 's|/var/run/nginx.pid|/app/nginx-tmp/nginx.pid|g' \
            -e 's|/run/nginx.pid|/app/nginx-tmp/nginx.pid|g' \
            /etc/nginx/nginx.conf \
    && mkdir -p /app/nginx-tmp/client_temp /app/nginx-tmp/proxy_temp \
               /app/nginx-tmp/fastcgi_temp /app/nginx-tmp/uwsgi_temp /app/nginx-tmp/scgi_temp \
    && chown -R nginx:nginx /app/nginx-tmp /usr/share/nginx/html

COPY --from=build --chown=nginx:nginx /app/dist/ /usr/share/nginx/html/

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
