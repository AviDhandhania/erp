#!/usr/bin/env bash
# Run as frappe. Build an independent bench without touching the active site's database.
set -Eeuo pipefail
umask 022
SOURCE="$(realpath "$1")"
DESTINATION="$2"
[[ ! -e $DESTINATION ]] || { echo 'Staging directory already exists.' >&2; exit 1; }
[[ -f $SOURCE/release.json ]] || { echo 'A verified release manifest is required.' >&2; exit 1; }
mkdir -p "$DESTINATION/.runtime"
python3 - "$SOURCE/release.json" "$DESTINATION/.runtime/pins.env" <<'PY'
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1]).parent/'deploy/release'))
from common import validate_manifest
m=validate_manifest(json.load(open(sys.argv[1])))
values={f'{k.upper()}_VERSION':v for k,v in m['runtime'].items()}
for app in ('frappe','erpnext'):
    values[app.upper()+'_REF']=m[app]['ref']
    values[app.upper()+'_COMMIT']=m[app]['commit']
Path(sys.argv[2]).write_text(''.join(f'{k}={v}\n' for k,v in values.items()))
PY
# shellcheck source=/dev/null
. "$DESTINATION/.runtime/pins.env"
curl -fsSL "https://astral.sh/uv/$UV_VERSION/install.sh" -o "$DESTINATION/.runtime/install-uv.sh"
UV_NO_MODIFY_PATH=1 UV_INSTALL_DIR="$DESTINATION/.runtime/bin" sh "$DESTINATION/.runtime/install-uv.sh"
NODE_ARCHIVE="node-v$NODE_VERSION-linux-x64.tar.xz"
curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/$NODE_ARCHIVE" -o "$DESTINATION/.runtime/$NODE_ARCHIVE"
curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt" -o "$DESTINATION/.runtime/SHASUMS256.txt"
(cd "$DESTINATION/.runtime" && awk -v file="$NODE_ARCHIVE" '$2==file' SHASUMS256.txt | sha256sum --check --strict -)
tar -xJf "$DESTINATION/.runtime/$NODE_ARCHIVE" -C "$DESTINATION/.runtime"
mv "$DESTINATION/.runtime/node-v$NODE_VERSION-linux-x64" "$DESTINATION/.runtime/node"
export PATH="$DESTINATION/.runtime/bin:$DESTINATION/.runtime/node/bin:$DESTINATION/.runtime/tools/bin:/usr/local/bin:/usr/bin:/bin"
npm install --global --prefix "$DESTINATION/.runtime/node" yarn@1.22.22
uv python install "$PYTHON_VERSION"
uv venv --python "$PYTHON_VERSION" "$DESTINATION/.runtime/tools"
uv pip install --python "$DESTINATION/.runtime/tools/bin/python" "frappe-bench==$BENCH_VERSION"
cp -a "$SOURCE" "$DESTINATION/source"
git -C "$DESTINATION/source" init -b main
git -C "$DESTINATION/source" add .
git -C "$DESTINATION/source" -c user.name=Installer -c user.email=installer@example.invalid commit -m 'Verified release source'
bench init "$DESTINATION/bench" --python "$DESTINATION/.runtime/tools/bin/python" \
    --frappe-branch "$FRAPPE_REF" --skip-assets --skip-redis-config-generation --no-backups
cd "$DESTINATION/bench"
[[ $(git -C apps/frappe rev-parse HEAD) == "$FRAPPE_COMMIT" ]] || { echo 'Frappe tag no longer matches the release manifest.' >&2; exit 1; }
bench get-app --branch "$ERPNEXT_REF" --skip-assets https://github.com/frappe/erpnext.git
[[ $(git -C apps/erpnext rev-parse HEAD) == "$ERPNEXT_COMMIT" ]] || { echo 'ERPNext tag no longer matches the release manifest.' >&2; exit 1; }
bench get-app --skip-assets "$DESTINATION/source"
ln -s "$DESTINATION/.runtime" .platform
cp "$SOURCE/release.json" .clothing-release.json
bench build --production
# nginx can traverse and read public assets, never private site files.
chmod o+x "$DESTINATION" "$DESTINATION/bench" sites apps apps/frappe apps/frappe/frappe apps/erpnext apps/erpnext/erpnext apps/clothing_erp apps/clothing_erp/clothing_erp
find -L sites/assets -type d -exec chmod o+rx {} +
find -L sites/assets -type f -exec chmod o+r {} +
touch .stage-complete
echo "Prepared independent bench: $DESTINATION/bench"
