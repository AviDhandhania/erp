#!/usr/bin/env bash
# GitHub ephemeral service test: exercise the same stage builder as install and update.
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo 'Run this through the GitHub compatibility workflow.' >&2; exit 1; }
set -Eeuo pipefail
SOURCE="$GITHUB_WORKSPACE"
exec > >(tee /tmp/clothing-compatibility.log) 2>&1
report_failure() {
    python3 - <<'DIAGNOSTIC'
from pathlib import Path
path=Path("/tmp/clothing-compatibility.log")
text="\n".join(path.read_text(errors="replace").splitlines()[-70:]) if path.exists() else "Native compatibility job failed before logging"
text=text[-12000:].replace("%","%25").replace("\r","%0D").replace("\n","%0A")
print("::error title=Native compatibility failure::"+text)
DIAGNOSTIC
}
trap report_failure ERR
VERSION="v$(python3 -c 'import ast; print(ast.literal_eval(open("clothing_erp/__init__.py").read().split("=",1)[1].strip()))')"
python3 deploy/release/build.py "$VERSION" --output /tmp/release-envelope
python3 - "$VERSION" <<'PYTHON'
import json,sys
from pathlib import Path
sys.path.insert(0,"deploy/release")
from common import extract_archive
directory=Path("/tmp/release-envelope")
extract_archive(directory/f"clothing-erp-{sys.argv[1]}.tar.gz",directory/"source")
(directory/"source/release.json").write_text((directory/"release.json").read_text())
PYTHON
# This is the SAME builder used by fresh LXC installs and customer updates.
bash /tmp/release-envelope/source/deploy/stage-release.sh /tmp/release-envelope/source /tmp/staged-release
export PATH="/tmp/staged-release/.runtime/tools/bin:/tmp/staged-release/.runtime/node/bin:/tmp/staged-release/.runtime/bin:$PATH"
cd /tmp/staged-release/bench
bench set-config -g redis_cache redis://127.0.0.1:6379/0
bench set-config -g redis_queue redis://127.0.0.1:6379/1
bench new-site test.local --db-host 127.0.0.1 --db-port 3306 --db-root-password test-only-ephemeral-password --admin-password test-only-admin --mariadb-user-host-login-scope '%'
bench --site test.local install-app erpnext
bench --site test.local install-app clothing_erp
bench --site test.local set-config -p allow_tests True
bench --site test.local migrate
bench --site test.local run-tests --app clothing_erp --test-category all
MYSQL_PWD=test-only-ephemeral-password /tmp/staged-release/.runtime/tools/bin/python "$SOURCE/deploy/tests/native_recovery.py" --socket /tmp/clothing-mariadb-socket/mysqld.sock
