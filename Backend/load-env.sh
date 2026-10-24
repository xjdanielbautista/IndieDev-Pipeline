#!/usr/bin/env bash

ENV_FILE="${1:-$(pwd)/.env.local}"
FORCE="${2:-}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "No existe $ENV_FILE"
    echo "Crea una copia con: cp .env.example .env.local"
    return 1 2>/dev/null || exit 1
fi

while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
        name="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        value="${value%\"}"
        value="${value#\"}"

        if [[ -z "${!name:-}" || "$FORCE" == "--force" ]]; then
            if [[ -n "$value" ]]; then
                export "${name}=${value}"
            fi
        fi
    fi
done < "$ENV_FILE"

if [[ -z "${SECRET_KEY:-}" ]]; then
    export SECRET_KEY="$(openssl rand -hex 32)"
fi

echo "Variables cargadas desde $(realpath "$ENV_FILE")"
echo "Las variables ya exportadas se conservan; usa: source load-env.sh .env.local --force"
