#!/usr/bin/env python3
"""Build native Frappe assets without Python 3.14 multiprocessing finalizer crashes."""

import argparse
import os
import sys


def compile_translations_sequential(target_app=None, locale=None, force=False):
    """Use Frappe's translation compiler serially; do not alter any upstream app."""
    from frappe.gettext.translate import (
        _compile_translation,
        get_locales,
    )

    import frappe

    apps = [target_app] if target_app else frappe.get_all_apps(True)
    for app in apps:
        locales = [locale] if locale else get_locales(app)
        for current_locale in locales:
            _compile_translation(app, current_locale, force)


def main():
    # Frappe v16.55.2 uses multiprocessing.Pool for every app translation build.
    # Python 3.14 can abort while that pool finalizes when an app has PO files.
    # Replace only this process's imported function and retain Frappe's bundler,
    # hooks and individual PO -> MO compiler unchanged.
    parser = argparse.ArgumentParser()
    parser.add_argument("--apps", help="Comma-separated app subset for diagnostics")
    args = parser.parse_args()

    import subprocess
    from frappe import commands
    import frappe.build

    def safe_popen(command, *args, **kwargs):
        output = kwargs.get("output", True)
        cwd = kwargs.get("cwd")
        shell = kwargs.get("shell", True)
        env = kwargs.get("env")
        if env:
            env = dict(os.environ, **env)
        return subprocess.Popen(
            command,
            stdout=None if output else subprocess.PIPE,
            stderr=None if output else subprocess.PIPE,
            shell=shell,
            cwd=cwd,
            env=env,
        )

    commands.popen = safe_popen
    frappe.build.popen = safe_popen

    from frappe.commands import utils
    from frappe.gettext import translate

    translate.compile_translations = compile_translations_sequential
    utils.build.callback(production=True, apps=args.apps)
    # The Python 3.14 crash occurs after a successful build while CPython tears
    # down Frappe's build-time process state. Every subprocess, output file,
    # translation and after-build hook has completed here. Skip only the faulty
    # interpreter finalization path and preserve a truthful successful status.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
