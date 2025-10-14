import argparse
import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_reconciliation(source_dir: Path, dest_dir: Path) -> None:
    """Sort files from source_dir into dest_dir by extension, logging duplicates."""
    if not source_dir.is_dir():
        logging.error("Source directory not found: %s", source_dir)
        return

    dest_dir.mkdir(parents=True, exist_ok=True)
    logging.info("Sorting and reconciliation started...")

    known_filenames = set()
    for existing in dest_dir.rglob('*'):
        if existing.is_file():
            known_filenames.add(existing.name)

    for item in source_dir.iterdir():
        if not item.is_file():
            continue

        filename = item.name
        extension = item.suffix.lower().lstrip('.') or 'no_ext'
        target_subdir = dest_dir / extension
        target_subdir.mkdir(exist_ok=True)
        target_path = target_subdir / filename

        if filename in known_filenames:
            logging.warning("Duplicate detected: '%s' already exists. Skipping.", filename)
            continue

        try:
            shutil.move(str(item), str(target_path))
        except Exception as exc:  # pragma: no cover
            logging.error("Failed to move %s: %s", filename, exc)
        else:
            known_filenames.add(filename)
            logging.info("Processed: '%s' -> '%s'", filename, target_subdir)

    logging.info("Reconciliation complete. Check destination directory for sorted files.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort files from a source directory into extension-based folders in the destination"
    )
    parser.add_argument('-s', '--src', required=True, help='Source directory')
    parser.add_argument('-d', '--dst', required=True, help='Destination directory')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = Path(args.src).expanduser().resolve()
    dest_dir = Path(args.dst).expanduser().resolve()
    run_reconciliation(source_dir, dest_dir)


if __name__ == "__main__":
    main()
