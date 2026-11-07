#!/usr/bin/env bash
# Produce a portable single-file installer; no GitHub credentials are packaged.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/dist/clothing-erp-lxc.run}"
mkdir -p "$(dirname "$OUT")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# Explicit allowlist excludes local bench, databases, credentials and history.
tar -C "$ROOT" --exclude=__pycache__ --exclude='*.pyc' -czf "$WORK/source.tar.gz" \
    clothing_erp deploy pyproject.toml README.md AGENTS.md license.txt work.md
DIGEST="$(sha256sum "$WORK/source.tar.gz" | awk '{print $1}')"
cat > "$OUT" <<'HEADER'
#!/usr/bin/env bash
set -Eeuo pipefail
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
LINE="$(awk '/^__CLOTHING_ERP_ARCHIVE__$/ {print NR+1; exit}' "$0")"
tail -n +"$LINE" "$0" > "$WORK/source.tar.gz"
HEADER
# shellcheck disable=SC2016,SC2129 # Write literal shell variables into the generated script.
printf 'printf '\''%%s  %%s\\n'\'' %s "$WORK/source.tar.gz" | sha256sum --check --status\n' "$DIGEST" >> "$OUT"
cat >> "$OUT" <<'HEADER'
mkdir "$WORK/source"
tar -xzf "$WORK/source.tar.gz" -C "$WORK/source"
if [[ ${1:-} == --extract ]]; then
    [[ $# -eq 2 ]] || { echo 'Usage: installer --extract DIRECTORY'; exit 1; }
    mkdir -p "$2"
    cp -a "$WORK/source/." "$2/"
    exit 0
fi
bash "$WORK/source/deploy/proxmox/install.sh"
exit
__CLOTHING_ERP_ARCHIVE__
HEADER
cat "$WORK/source.tar.gz" >> "$OUT"
chmod +x "$OUT"
echo "$OUT"
