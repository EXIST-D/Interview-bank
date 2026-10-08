#!/bin/sh
# Set the login for the hosted Web reader. Run it yourself on the server: the password is typed here only.
set -eu
FILE=/etc/nginx/interview-bank.htpasswd
printf 'Username: '; read -r USERNAME
case "$USERNAME" in ''|*:*) echo "A username without ':' is required" >&2; exit 1;; esac
stty -echo; printf 'Password: '; read -r PASSWORD; printf '\nRepeat: '; read -r AGAIN; stty echo; echo
[ "$PASSWORD" = "$AGAIN" ] || { echo "Passwords differ" >&2; exit 1; }
[ ${#PASSWORD} -ge 10 ] || { echo "Use at least 10 characters" >&2; exit 1; }
HASH=$(printf '%s' "$PASSWORD" | openssl passwd -apr1 -stdin)
printf '%s:%s\n' "$USERNAME" "$HASH" > "$FILE"
chown root:www-data "$FILE"; chmod 640 "$FILE"
echo "Login set for $USERNAME. Open https://<your site>/ibank/"
