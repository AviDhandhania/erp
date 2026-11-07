# Clothing ERP (`clothing_erp`)

> Open-source apparel distribution ERP built on Frappe Framework and ERPNext.

---

## 1. Overview & Stage 1 Scope

`clothing_erp` is a specialized distribution extension for ERPNext tailored for wholesale apparel distributors, fashion brand intermediaries, and garment supply chains.

This repository represents **Stage 1: Development Environment and Custom App Foundation**.

### Navigation Placeholders (Stage 1 Foundation)
The app provides a unified portal homepage (`/` or `/clothing`) with 7 primary operational placeholders:
- **Admin**: User roles, access controls, and system configuration.
- **Products**: Garment catalog, style codes, size/color variant matrix, and wholesale price lists.
- **Sales**: B2B wholesale distribution orders, quotations, and commercial invoices.
- **Retailers**: Boutique and department store accounts, credit lines, and customer groups.
- **Warehouse**: Inventory balances, bin allocation, pick-lists, and stock transfers.
- **Suppliers**: Garment manufacturers, fabric mills, trim vendors, and purchase orders.
- **Reports**: Sell-through analytics, gross margin analysis, and inventory aging.

*(Note: Business logic, custom DocTypes, and automated workflows for products, sales, and warehouse will be added in subsequent stages.)*

---

## 2. Core Architecture Rules

1. **Zero Core Modifications**: Never modify Frappe Framework or ERPNext core code. All custom logic, overrides, hooks, and extensions reside exclusively in `clothing_erp`.
2. **Reuse Upstream DocTypes**: Utilize native ERPNext models (`Item`, `Sales Order`, `Customer`, `Stock Entry`, `Supplier`, `Purchase Order`) rather than creating duplicate ledgers.
3. **Server-Side Security**: Enforce all permissions, validation, and business rules in Python server controllers. Client-side UI controls are for convenience only.
4. **Isolated Git Repositories**: This repository is independent of the upstream ERPNext and Frappe repositories.
5. **Deployment Parity**: Kept 100% compatible with standard Docker Compose setups and Proxmox LXC container deployments.

---

## 3. Technology Stack & Pinned Versions

- **Frappe Framework**: `version-16` (`v16.55.2`)
- **ERPNext**: `version-16` (`v16.54.0`)
- **Python**: 3.11 (or 3.12)
- **Node.js**: 18.x / 20.x
- **MariaDB**: 11.4 / 10.6 LTS (configured with `utf8mb4` and `innodb-snapshot-isolation=OFF`)
- **Redis**: 7.x (Cache & Queue)

---

## 4. Commands: Start, Stop, Test & Maintain

### Docker Compose Environment (Recommended)

#### Start Services
```bash
# Start all containers in background
docker compose up -d

# Check running container status
docker compose ps
```

#### Run Bench Inside Container
```bash
# Open interactive shell in Frappe container
docker compose exec frappe bash

# Inside container: start development bench
bench start
```

#### Stop Services
```bash
# Stop containers gracefully
docker compose down

# Stop and remove volumes (reset site data)
docker compose down -v
```

### Automated Testing
```bash
# Run standalone unit tests
python -m unittest discover -s clothing_erp/tests

# Run tests within Frappe Bench site
bench --site dev.clothing.local run-tests --app clothing_erp
```

### Maintenance Commands
```bash
# Apply migrations after pulling changes
bench --site dev.clothing.local migrate

# Build frontend assets
bench build --app clothing_erp

# Clear site cache
bench --site dev.clothing.local clear-cache
```

---

## 5. License
MIT License. See [license.txt](license.txt) for details.
