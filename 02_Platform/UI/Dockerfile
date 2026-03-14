# Stage 1: build React app
# Build context must be the repo root so platform packages are accessible if needed.
FROM node:20-alpine AS builder
WORKDIR /app
COPY 02_Platform/UI/react/package*.json ./
RUN npm ci
COPY 02_Platform/UI/react/ ./
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist           /usr/share/nginx/html
COPY 02_Platform/UI/nginx.conf          /etc/nginx/conf.d/default.conf
EXPOSE 80
