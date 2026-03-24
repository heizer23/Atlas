# Stage 1: build the Atlas Shell Vite application
#
# Build context is the repo root so application source paths resolve correctly.
# platform-ui lives inside the shell at 02_Platform/02_Atlas_Shell/platform-ui/
# and is covered by the shell COPY below — no separate copy needed.
#
FROM node:20-alpine AS builder

WORKDIR /repo

# Install shell dependencies
COPY 02_Platform/02_Atlas_Shell/package*.json 02_Platform/02_Atlas_Shell/
RUN cd 02_Platform/02_Atlas_Shell && npm ci

# Copy shell source (includes platform-ui/)
COPY 02_Platform/02_Atlas_Shell/ 02_Platform/02_Atlas_Shell/

# Copy application shell registration files.
# main.tsx imports these as side-effects; Vite must see them at build time.
# Add a new COPY line here when a new application is integrated into the shell.
COPY 03_Application/WorkoutTracker/src/ 03_Application/WorkoutTracker/src/
COPY 03_Application/TaskTracker/src/    03_Application/TaskTracker/src/
COPY 03_Application/FoodTracker/src/    03_Application/FoodTracker/src/
COPY 03_Application/Chronicle/src/      03_Application/Chronicle/src/

WORKDIR /repo/02_Platform/02_Atlas_Shell
RUN npm run build

# Stage 2: serve with nginx (SPA fallback + API proxy)
FROM nginx:alpine
COPY --from=builder /repo/02_Platform/02_Atlas_Shell/dist  /usr/share/nginx/html
COPY 02_Platform/02_Atlas_Shell/nginx.conf                 /etc/nginx/conf.d/default.conf
EXPOSE 80
