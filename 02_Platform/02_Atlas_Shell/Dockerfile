# Stage 1: build the Atlas Shell Vite application
#
# Build context must be the repo root so the @platform-ui alias
# (vite.config.ts: '../../02_Platform/UI/react/src/') resolves correctly.
# The shell vite.config.ts uses path.resolve(__dirname, ...) relative to the
# shell package root — at build time __dirname is /app, so we reproduce
# the same relative structure inside the image.
#
FROM node:20-alpine AS builder

# Recreate the relevant repo subtree under /repo so relative paths match.
WORKDIR /repo

# Install shell dependencies
COPY 02_Platform/02_Atlas_Shell/package*.json 02_Platform/02_Atlas_Shell/
RUN cd 02_Platform/02_Atlas_Shell && npm ci

# Copy Platform UI source (alias target: /repo/02_Platform/UI/react/src/)
COPY 02_Platform/UI/react/src/ 02_Platform/UI/react/src/

# Copy shell source
COPY 02_Platform/02_Atlas_Shell/ 02_Platform/02_Atlas_Shell/

# Copy application shell registration files.
# main.tsx imports these as side-effects; Vite must see them at build time.
# Add a new COPY line here when a new application is integrated into the shell.
COPY 03_Application/WorkoutTracker/src/ 03_Application/WorkoutTracker/src/
COPY 03_Application/TaskTracker/src/    03_Application/TaskTracker/src/

WORKDIR /repo/02_Platform/02_Atlas_Shell
RUN npm run build

# Stage 2: serve with nginx (SPA fallback + API proxy)
FROM nginx:alpine
COPY --from=builder /repo/02_Platform/02_Atlas_Shell/dist  /usr/share/nginx/html
COPY 02_Platform/02_Atlas_Shell/nginx.conf                 /etc/nginx/conf.d/default.conf
EXPOSE 80
