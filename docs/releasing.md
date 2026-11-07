# Releases without coordinating three repositories

For routine development, change only the Clothing ERP app, commit, and push.
The `Verify app and installer` workflow runs app tests, release/update fault tests,
ShellCheck, Python checks and a fresh database-backed native Frappe/ERPNext install.
It builds the frontend and runs the app's real site tests against the pinned core.
Dependabot proposes weekly updates for GitHub Actions dependencies.

To ship: GitHub → Actions → **Publish release** → **Run workflow**. Enter the next
stable `vMAJOR.MINOR.PATCH`; leave upstream fields empty unless updating them.
The action can write the version bump to main and create its tag using the
repository's built-in GITHUB_TOKEN. No hosting key, registry account, SSH deployment
key or customer credential is required. If main is later protected, explicitly
permit the release bot's version commit or prepare the bump/tag in a PR instead.

The workflow supports an ordinary pushed tag too. In that case, commit the matching
`clothing_erp/__init__.py` version first. It refuses tag/version mismatches. Published
assets are never replaced: use a new version for a correction. A failed draft may
be retried, using the same tagged source. Serialized publication prevents two
releases racing to become latest.

A release is built from a clean Git commit. The source tar uses `git archive`, not
a recursive copy of a developer's directory. The builder resolves annotated or
lightweight upstream tags to full commits. Installation refuses a core tag that no
longer resolves to that release's recorded commit.

CI first resolves the environment, freezes every installed runtime Python package
(including the Bench tools environment), then builds and tests a second fresh bench
using those exact versions. Only the lock files from that passing build are included
in the published source archive. Installers verify their checksums, constrain package
installation, and compare the complete installed package lists against the locks.
Node dependency versions come from the pinned upstream yarn.lock files; source-tree
checks reject builds that rewrite upstream tracked files. Debian system libraries
and package security updates remain distribution-managed, so this is version-locked
application reproducibility rather than a claim of byte-identical OS images.

Artifacts:

- `clothing-erp-vX.Y.Z.tar.gz`: the custom app and its deployment tools.
- `release.json`: exact source/core/runtime contract and source archive checksum.
- `SHA256SUMS`: checksums for manifest, archive and portable installer.
- `clothing-erp-lxc.run`: self-extracting installer containing the app/manifest.
- GitHub build-provenance attestation for the artifacts.

The workflow uploads to a draft only after all verification jobs succeed, then
publishes the completed draft as latest. Customers are not sent a partly uploaded
release. The installed client excludes drafts, prereleases, invalid manifests and
missing/corrupt artifacts. No release is built from a moving production main branch.
The small entrypoint bootstrap may be read from main; the deployed code is always
selected from a published stable release.

## ERPNext and Frappe updates

The apps remain independent. Their current stable pins are in `deploy/versions.env`.
A normal clothing release keeps those pins. For a core update, select the desired
stable **v16** tag in the release form or commit the pin change normally. The same
compatibility jobs gate the resulting distribution release. Runtime patch updates
are similarly declared in `versions.env` and built into a new environment.

The current platform supports Debian 13, Python 3.14, Node 24 LTS and core v16. A
major framework/runtime/platform transition needs a separately tested platform
migration and new manifest schema; never sneak it into a clothing feature release.
The updater rejects core/runtime downgrades and mutable upstream tag commits.

## First release and testing limits

An empty repository has no installable stable release. Publish the first successful
release before distributing the install command. A tag with failed CI is not a
production release.

CI tests the real native application combination plus file-backed update failure
and rollback scenarios. The Proxmox host-command tests use command doubles. The
full native guest provisioning, actual service/DB restore, reboot persistence and
host-specific networking still require a disposable real Proxmox CT trial. Retain
that distinction in release notes and do not describe the installer as universally
validated across hosts.
