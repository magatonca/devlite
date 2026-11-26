#!/usr/bin/env python3
"""Download only the three approved pinned archives; no installation."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.final_acquisition import acquire
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan-sha256',required=True);p.add_argument('--download-authorized',action='store_true',required=True);a=p.parse_args()
 try:print(acquire(ROOT,a.plan_sha256,a.download_authorized))
 except (OSError,ValueError) as error:raise SystemExit(str(error))
