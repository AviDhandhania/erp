"""Exercise host installer control flow with command doubles inside an unprivileged user namespace.
No actual Proxmox resources, packages, databases or system services are changed.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
STUB = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
with open(os.environ['COMMAND_LOG'],'a') as log: log.write(json.dumps([name,*args])+'\\n')
mode=os.environ.get('TEST_MODE','')
if name=='pvesm':
    print('Name Type Status Total Used Available %')
    if mode!='missing-storage': print('local dir active 100000000 0 100000000 0%')
elif name=='pvesh':
    if '--vmid' in args and mode=='existing-vmid': sys.exit(1)
    print('101')
elif name=='pveam' and args[0]=='available':
    if mode!='no-template': print('system debian-13-standard_13.1-1_amd64.tar.zst')
elif name=='pct':
    if 'hostname' in args: print('10.0.0.50')
    if 'bash' in args and mode=='guest-failure': sys.exit(1)
'''


class TestInstaller(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe=subprocess.run(['unshare','-Ur','true'],capture_output=True)
        if probe.returncode:
            raise unittest.SkipTest('Unprivileged user namespaces unavailable')

    def run_installer(self, mode='', **settings):
        with tempfile.TemporaryDirectory() as directory:
            tmp=Path(directory)
            for name in ('pct','pveam','pvesh','pvesm','ip'):
                path=tmp/name
                path.write_text(STUB)
                path.chmod(0o755)
            env=os.environ | {'PATH':f'{tmp}:'+os.environ['PATH'], 'COMMAND_LOG':str(tmp/'calls.jsonl'), 'TEST_MODE':mode} | settings
            result=subprocess.run(['unshare','-Ur','bash',str(ROOT/'deploy/proxmox/install.sh')],env=env,capture_output=True,text=True,timeout=30)
            calls=[json.loads(line) for line in (tmp/'calls.jsonl').read_text().splitlines()] if (tmp/'calls.jsonl').exists() else []
            self.assertFalse(any(call[0]=='pct' and call[1] in ('destroy','stop') for call in calls))
            return result,calls

    def test_creates_new_unprivileged_container_with_http_address(self):
        result,calls=self.run_installer()
        self.assertEqual(result.returncode,0,result.stderr)
        create=next(call for call in calls if call[:2]==['pct','create'])
        self.assertEqual(create[create.index('--unprivileged')+1],'1')
        self.assertIn('http://10.0.0.50/',result.stdout)
        self.assertTrue(any('install-debian.sh' in ' '.join(call) for call in calls))

    def test_existing_id_is_rejected_before_create(self):
        result,calls=self.run_installer('existing-vmid',CTID='101')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(call[:2]==['pct','create'] for call in calls))

    def test_missing_storage_is_rejected_before_create(self):
        result,calls=self.run_installer('missing-storage')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(call[:2]==['pct','create'] for call in calls))

    def test_failed_guest_install_preserves_container(self):
        result,calls=self.run_installer('guest-failure')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('preserved for diagnosis',result.stderr)

    def test_static_network_requires_gateway(self):
        result,calls=self.run_installer(CT_IP='10.0.0.50/24',GATEWAY='')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(call[:2]==['pct','create'] for call in calls))

    def test_insufficient_resources_rejected(self):
        result,calls=self.run_installer(MEMORY='1024')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(call[:2]==['pct','create'] for call in calls))

    def test_missing_template_rejected(self):
        result,calls=self.run_installer('no-template')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(call[:2]==['pct','create'] for call in calls))


class TestPackage(unittest.TestCase):
    def test_portable_installer_extracts_same_source_without_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'install.run'
            extracted=Path(directory)/'extracted'
            subprocess.run(['bash',str(ROOT/'deploy/build-installer.sh'),str(output)],check=True,capture_output=True)
            subprocess.run(['bash',str(output),'--extract',str(extracted)],check=True,capture_output=True)
            self.assertEqual((extracted/'clothing_erp/security.py').read_bytes(),(ROOT/'clothing_erp/security.py').read_bytes())
            self.assertTrue((extracted/'deploy/proxmox/install.sh').exists())
            for forbidden in ('.git','sites','.services','.venv','site_config.json'):
                self.assertFalse(list(extracted.rglob(forbidden)))
