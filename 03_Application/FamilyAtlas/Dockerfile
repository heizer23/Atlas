# Static site, served readonly behind HTTP Basic Auth (see nginx.conf).
# No build step — index.html/css/js/data are plain files.
FROM nginx:alpine

RUN apk add --no-cache apache2-utils

COPY index.html /usr/share/nginx/html/index.html
COPY css/       /usr/share/nginx/html/css/
COPY js/        /usr/share/nginx/html/js/
COPY data/      /usr/share/nginx/html/data/

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.d/20-generate-htpasswd.sh /docker-entrypoint.d/20-generate-htpasswd.sh
RUN chmod +x /docker-entrypoint.d/20-generate-htpasswd.sh

EXPOSE 80
