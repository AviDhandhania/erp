#!/usr/bin/env python3
"""Compatibility launcher for the real local stack."""
import os
from pathlib import Path
script = Path(__file__).resolve().parent.parent / "scripts/start_all.sh"
os.execv(str(script), [str(script)])
