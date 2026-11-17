# Current implementation and certification status

Last reconciled: 2026-11-18 (Asia/Kolkata)

## Implemented scope

Sessions 1–18 of the production programme in [`../work.md`](../work.md) are committed:

- security audit, authorization, API/file/privacy and deployment hardening;
- signed supply chain, SBOMs, encrypted backup and recovery tooling;
- complete Sales, Warehouse and Quality server workflows;
- barcode generation, scan resolution, audited PDF/ZPL labels and web scanning;
- shared Flutter foundation and separate Sales, Warehouse and Quality mobile targets.

The custom Frappe installation consists of `sales_erp`, `warehouse_erp` and `quality_erp`.
The former `clothing_erp` Frappe application has been removed. ERPNext, Frappe, Insights and
India Compliance remain pinned upstream dependencies and must not be modified in this repo.

## Not yet production-certified

Implementation completion is not production certification. The following remain open:

- Session 19 full fresh-install, cross-app, browser, real-device mobile, hardware scanner,
  printer, penetration, concurrency, load, failure-injection and migration certification;
- a real disposable Proxmox install/update/reboot/backup/restore/rollback drill;
- independent review and remediation of every critical/high security finding;
- Session 20 signed stable server/mobile release and final operational acceptance.

Until those gates pass, mobile applications and the next server release are release
candidates, not production-certified builds.

## Private repository operation

The GitHub repository and its release assets are private. Installation and updates require
a fine-grained GitHub token with **Contents: Read-only** access, supplied transiently through
`CLOTHING_ERP_GITHUB_TOKEN`. The token must not be committed, embedded in URLs, copied into
the LXC, or persisted in Frappe/systemd configuration.

See [`releasing.md`](releasing.md), [`operations.md`](operations.md), the
[security documentation](security/), [barcode design](barcodes.md), and
[mobile ADR](adr/ADR-001-mobile-framework-selection.md).
