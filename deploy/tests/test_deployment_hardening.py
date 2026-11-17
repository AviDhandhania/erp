# Copyright (c) 2026, Clothing ERP Contributors
# License: MIT. See LICENSE

"""Automated validation of Session 5 Deployment, TLS, Systemd, and Host Hardening Invariants."""

import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

DEPLOY_DIR = Path(__file__).resolve().parents[1]


class TestDeploymentHardening(unittest.TestCase):
    """Assert deployment security controls, TLS configuration, systemd sandboxing, and firewall rules."""

    def setUp(self):
        self.nginx_conf = (DEPLOY_DIR / "nginx.conf").read_text(encoding="utf-8")
        self.install_debian = (DEPLOY_DIR / "install-debian.sh").read_text(encoding="utf-8")
        self.proxmox_install = (DEPLOY_DIR / "proxmox" / "install.sh").read_text(encoding="utf-8")
        self.proxmox_fw = (DEPLOY_DIR / "proxmox" / "clothing-erp.fw").read_text(encoding="utf-8")

    def test_nginx_enforces_http_to_https_redirect(self):
        """Port 80 must unconditionally redirect all traffic to HTTPS via 301."""
        self.assertIn("listen 80 default_server;", self.nginx_conf)
        self.assertIn("return 301 https://$host$request_uri;", self.nginx_conf)
        # ACME challenge location must exist on port 80
        self.assertIn("location ^~ /.well-known/acme-challenge/", self.nginx_conf)

    def test_nginx_enforces_modern_tls_and_ciphers(self):
        """Port 443 must listen on SSL and enforce TLS 1.2+ with modern cipher suites."""
        self.assertIn("listen 443 ssl default_server;", self.nginx_conf)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", self.nginx_conf)
        self.assertIn("ssl_certificate /etc/ssl/clothing-erp/cert.pem;", self.nginx_conf)
        self.assertIn("ssl_certificate_key /etc/ssl/clothing-erp/key.pem;", self.nginx_conf)
        self.assertIn("ssl_prefer_server_ciphers off;", self.nginx_conf)

    def test_nginx_enforces_all_required_security_headers(self):
        """Nginx must set HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer, and Permissions policies."""
        headers = [
            'Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"',
            "X-Content-Type-Options nosniff",
            "X-Frame-Options SAMEORIGIN",
            'Referrer-Policy "strict-origin-when-cross-origin"',
            "Permissions-Policy",
            "Content-Security-Policy",
        ]
        for header in headers:
            self.assertIn(header, self.nginx_conf, f"Missing required security header: {header}")

    def test_nginx_blocks_direct_access_to_private_and_protected_files(self):
        """Direct browser requests to /protected/ and /private/ must return 404."""
        self.assertIn("location /protected/ { return 404; }", self.nginx_conf)
        self.assertIn("location ^~ /private/ { return 404; }", self.nginx_conf)

    def test_systemd_units_enforce_full_sandboxing(self):
        """Every rendered systemd service unit must include strict sandbox and isolation directives."""
        render_path = DEPLOY_DIR / "render-services.py"
        spec = importlib.util.spec_from_file_location("render_services", render_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            module.render(tmpdir)
            units = list(Path(tmpdir).glob("*.service"))
            self.assertEqual(len(units), 4)

            required_directives = [
                "NoNewPrivileges=yes",
                "ProtectSystem=strict",
                "ProtectHome=read-only",
                "PrivateTmp=yes",
                "PrivateDevices=yes",
                "ProtectKernelTunables=yes",
                "ProtectKernelModules=yes",
                "ProtectControlGroups=yes",
                "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
                "RestrictNamespaces=yes",
                "LockPersonality=yes",
                "MemoryDenyWriteExecute=no",
                "ReadWritePaths=",
                "User=frappe",
            ]

            for unit in units:
                content = unit.read_text(encoding="utf-8")
                for directive in required_directives:
                    self.assertIn(
                        directive,
                        content,
                        f"Unit {unit.name} missing security sandboxing directive: {directive}",
                    )

    def test_mariadb_binds_strictly_to_localhost(self):
        """MariaDB server configuration must bind exclusively to 127.0.0.1."""
        self.assertIn("bind-address=127.0.0.1", self.install_debian)
        self.assertIn("innodb-snapshot-isolation=OFF", self.install_debian)

    def test_initial_administrator_credential_file_mode(self):
        """Initial credentials must be stored strictly with mode 0600."""
        self.assertIn("chmod 600 /root/clothing-erp-credentials", self.install_debian)
        self.assertIn("https://", self.install_debian)
        self.assertNotIn("http://%s/\\nUser: Administrator", self.install_debian)

    def test_proxmox_lxc_firewall_rules(self):
        """Proxmox container firewall must enforce default drop and allow only ports 443 and 80."""
        self.assertIn("policy_in: DROP", self.proxmox_fw)
        self.assertIn("policy_out: ACCEPT", self.proxmox_fw)
        self.assertIn("IN ACCEPT -p tcp -dport 443", self.proxmox_fw)
        self.assertIn("IN ACCEPT -p tcp -dport 80", self.proxmox_fw)
        self.assertIn("IN DROP -p tcp -dport 3306", self.proxmox_fw)
        self.assertIn("IN DROP -p tcp -dport 6379", self.proxmox_fw)


if __name__ == "__main__":
    unittest.main()
