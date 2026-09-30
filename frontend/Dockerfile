# NEXUS Console - production static build + serve (Phase 7).
#
# Uses the existing Vite production build (`npm run build`, unchanged --
# see package.json) and serves the resulting static assets with nginx. This
# does not run the Vite dev server, and does not introduce a Node.js
# runtime into the final image -- only static files + nginx.
#
# The Console's API base URL (VITE_NEXUS_API_BASE_URL) is a Vite
# build-time value baked into the compiled JS bundle (see
# src/lib/config.ts) -- there is no server-side templating here, exactly as
# the existing `vite build` behavior already works locally. Pass it as a
# build argument to point a built image at a specific NEXUS API without
# modifying source. VITE_NEXUS_API_TOKEN is deliberately NOT accepted as a
# build argument here: per ARCHITECTURE.md/CLAUDE.md, that value is not a
# secret but is only appropriate for a trusted local/demo browser, never
# baked into a shared or distributed image -- configure it at runtime via a
# per-deployment rebuild only if that specific use case is truly needed.

FROM node:20-alpine AS build

WORKDIR /app

# Dependency install layer cached independently of source changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_NEXUS_API_BASE_URL=http://127.0.0.1:8000
ENV VITE_NEXUS_API_BASE_URL=${VITE_NEXUS_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine AS runtime

LABEL org.opencontainers.image.title="nexus-console" \
      org.opencontainers.image.description="NEXUS Console - AI Agent Runtime & Orchestration Platform UI"

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

# nginx's own image already runs as an unprivileged `nginx` user for the
# worker processes; no additional user setup needed here.
CMD ["nginx", "-g", "daemon off;"]
