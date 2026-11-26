#!/usr/bin/env python3
"""Resolve all bundle ELF dependencies and immediate symbols against extracted core22."""
import argparse
from pathlib import Path
import subprocess
import tempfile


PROBE = r'''
#include <dlfcn.h>
#include <stdio.h>
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (!dlopen(argv[1], RTLD_NOW | RTLD_LOCAL)) {
        fprintf(stderr, "%s\n", dlerror());
        return 1;
    }
    return 0;
}
'''


def main(bundle, core, official):
    roots = (bundle / 'lib', official, core)
    loader = core / 'ld-linux-x86-64.so.2'
    prefix = [str(loader), '--inhibit-cache', '--library-path', ':'.join(map(str, roots))]
    binary = bundle / 'ubuntu_bootstrap'
    libs = sorted((bundle / 'lib').glob('*.so'))
    if not binary.is_file() or not libs:
        raise SystemExit('Incomplete Flutter bundle')
    failed = False
    with tempfile.TemporaryDirectory(prefix='devlite-v7-abi-') as path:
        source = Path(path) / 'probe.c'
        probe = source.with_suffix('')
        source.write_text(PROBE)
        subprocess.run(['/usr/bin/cc', '-o', probe, source, '-ldl'], check=True, timeout=60)
        for item in [binary, *libs]:
            listed = subprocess.run([*prefix, '--list', item], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, timeout=60)
            providers = (line.split('=> ', 1)[1].split()[0]
                         for line in listed.stdout.splitlines() if '=> ' in line)
            foreign = [provider for provider in providers if not any(
                Path(provider).resolve().is_relative_to(root) for root in roots)]
            if listed.returncode or foreign:
                failed = True
                print(item.name, listed.stdout.strip(), 'unexpected providers:', foreign)
            if item != binary:
                result = subprocess.run([*prefix, probe, item], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, timeout=60)
                failed |= result.returncode != 0
                print(item.name, result.stdout.strip() or 'OK')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'core', 'official'):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    main(args.bundle, args.core, args.official)
