FROM nginx:1.27-alpine

# htpasswd (for hashing the Basic Auth password) ships in apache2-utils.
RUN apk add --no-cache apache2-utils

COPY nginx.conf /etc/nginx/nginx.conf

# Startup hook: builds .htpasswd + auth.conf from GATEWAY_PASSWORD at boot.
# The official nginx image runs every *.sh in /docker-entrypoint.d/ before
# starting nginx, so the auth files exist by the time the config is parsed.
COPY 00-gateway-auth.sh /docker-entrypoint.d/00-gateway-auth.sh
RUN chmod +x /docker-entrypoint.d/00-gateway-auth.sh

# Guarantee the included file exists even before the hook runs, so
# `include /etc/nginx/auth.conf;` can never fail on a cold parse.
RUN touch /etc/nginx/auth.conf

EXPOSE 80
