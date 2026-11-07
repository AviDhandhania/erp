#!/usr/bin/env python3
import argparse
from common import fetch_release

parser = argparse.ArgumentParser()
parser.add_argument("destination")
parser.add_argument("--version")
args = parser.parse_args()
manifest, source = fetch_release(args.destination, args.version)
print(f"Verified {manifest['version']} at {source}")
