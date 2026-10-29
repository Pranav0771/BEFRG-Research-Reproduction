"""Audit the presence and provenance of committed Phase 2–4 result files.

Does NOT claim that the numbers were regenerated on the current hardware.
Run: python -m scripts.verify_results
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'phase2': 'results/tables/phase2_paper_ours_overview.csv',
    'phase3': 'results/phase3/grid_comparison.csv',
    'phase4': 'results/phase4/use_cases.csv',
    'phase4_inputs': 'results/phase4/scenario_inputs.json',
    'original_montoya_extension': 'results/montoya_extension1/extension1_g_original_xml.csv',
}


def _verify_manifest() -> None:
    """Verify archived CSV, JSON and PNG bytes against the committed manifest."""
    manifest = ROOT / 'results/MANIFEST.sha256'
    if not manifest.is_file():
        raise SystemExit('Missing results/MANIFEST.sha256')
    checked = 0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split('  ', 1)
        except ValueError as exc:
            raise SystemExit(f'Invalid manifest line: {line}') from exc
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f'Missing result from manifest: {relative}')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Checksum mismatch for {relative}. Regeneration may change outputs.')
        checked += 1
    print(f'OK committed-result checksums: {checked} files')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-hashes', action='store_true',
                        help='verify exact archive contents against results/MANIFEST.sha256')
    args = parser.parse_args()
    for label, relative in EXPECTED.items():
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f'Missing/empty result artifact: {relative}')
        print(f'OK {label}: {relative}')
    for relative in (
        'results/phase3/grid_comparison.csv',
        'results/phase4/use_cases.csv',
    ):
        with (ROOT / relative).open(newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise SystemExit(f'No result records: {relative}')
        if any(row.get('provenance', '').strip('[]') != 'ours-scaled-down' for row in rows):
            raise SystemExit(f'Mislabeled provenance in {relative}')
        print(f'OK provenance: {relative} ({len(rows)} rows)')
    # Saved original-XML results have a separate provenance label from the
    # Phase 2–4 synthetic surrogates. The external XML source is not bundled.
    with (ROOT / 'results/montoya_extension1/extension1_g_original_xml.csv').open(
            newline='', encoding='utf-8') as src:
        recorded = list(csv.DictReader(src))
    if len(recorded) != 8 or any('original-XML' not in r['provenance'] for r in recorded):
        raise SystemExit('Invalid original-XML Extension 1 result provenance')
    data_path = ROOT / 'data/raw/montoya'
    for archive in data_path.glob('**/*'):
        if archive.is_file() and archive.name != '.gitkeep':
            print(f'INFO: user-provided source benchmark present: {archive.name}')
    if args.check_hashes:
        _verify_manifest()
    print('This is an artifact-integrity audit, not a full numerical reproduction test.')


if __name__ == '__main__':
    main()
