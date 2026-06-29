#!/bin/sh
# ───────────────────────────────────────────────────────────────
# Runs automatically at container start via the official nginx image's
# /docker-entrypoint.d/ mechanism (any *.sh there is executed before
# nginx launches). We do NOT exec nginx ourselves — the base image
# does that after all hook scripts finish.
#
# Turns a PLAINTEXT password (GATEWAY_PASSWORD in .env) into the hashed
# .htpasswd file Basic Auth needs, fresh on every start. Change the
# password = edit .env, restart nginx. No manual htpasswd ritual.
#
# Empty GATEWAY_PASSWORD → auth DISABLED (open, for pure local dev).
# ───────────────────────────────────────────────────────────────
set -eu

HTPASSWD_FILE="/etc/nginx/.htpasswd"
AUTH_INCLUDE="/etc/nginx/auth.conf"
USER="${GATEWAY_USER:-demo}"

if [ -n "${GATEWAY_PASSWORD:-}" ]; then
  htpasswd -cbB "$HTPASSWD_FILE" "$USER" "$GATEWAY_PASSWORD" >/dev/null 2>&1
  cat > "$AUTH_INCLUDE" <<EOF
auth_basic "Medical AI Gateway — demo access";
auth_basic_user_file ${HTPASSWD_FILE};
EOF
  echo "[gateway-auth] Basic Auth ENABLED for user '${USER}'"
else
  : > "$AUTH_INCLUDE"
  echo "[gateway-auth] Basic Auth DISABLED (GATEWAY_PASSWORD empty)"
fi
