#!/bin/sh
# Git credential helper that reads GITHUB_TOKEN from the environment at runtime.
# Referenced from .git/config so that plain `git fetch origin` works in the shell.
# The token itself is never stored in git config or source control.
#
# Security: only returns credentials for https://github.com requests.

case "$1" in
  get)
    input=$(cat)
    protocol=$(printf '%s' "$input" | grep '^protocol=' | cut -d= -f2)
    host=$(printf '%s' "$input" | grep '^host=' | cut -d= -f2)
    if [ "$protocol" = "https" ] && [ "$host" = "github.com" ]; then
      echo "username=token"
      echo "password=${GITHUB_TOKEN}"
    fi
    ;;
esac
