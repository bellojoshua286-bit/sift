import hashlib
import os
import stat

PARTIAL_SIZE = 64 * 1024   # 64 KB
CHUNK_SIZE = 1024 * 1024   # 1 MB
IGNORED_PREFIXES = ("~$",)  # Office temporary lock files
HIDDEN_FLAGS = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM


def scan_folder(folder_path, include_hidden=False):
    """List every file in a folder and its subfolders.
    Returns a list of (file_path, file_size) pairs.
    Hidden/system files and Office lock files are skipped
    unless include_hidden=True."""
    files = []
    pending = [folder_path]

    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                        attributes = getattr(info, "st_file_attributes", 0)

                        if not include_hidden and attributes & HIDDEN_FLAGS:
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            pending.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if not include_hidden and entry.name.startswith(
                                IGNORED_PREFIXES
                            ):
                                continue
                            files.append((entry.path, info.st_size))
                    except OSError:
                        continue
        except OSError:
            continue

    return files


def group_by_size(files):
    """Group files by size. Sizes with only one file are removed."""
    groups = {}

    for path, size in files:
        if size == 0:
            continue
        if size not in groups:
            groups[size] = []
        groups[size].append(path)

    same_size = {}
    for size, paths in groups.items():
        if len(paths) > 1:
            same_size[size] = paths

    return same_size


def hash_file(path, partial=False):
    """Return a fingerprint (hash) of a file's contents.
    partial=True hashes only the first 64 KB (fast).
    partial=False hashes the whole file.
    Returns None if the file can't be read."""
    hasher = hashlib.blake2b()

    try:
        with open(path, "rb") as f:
            if partial:
                hasher.update(f.read(PARTIAL_SIZE))
            else:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
    except OSError:
        return None

    return hasher.hexdigest()


def group_by_hash(paths, partial):
    """Sort a list of file paths by their hash. Hashes are used only
    internally. Returns a list of groups (each a list of paths),
    keeping only groups with 2 or more files."""
    groups = {}

    for path in paths:
        digest = hash_file(path, partial=partial)
        if digest is None:
            continue
        if digest not in groups:
            groups[digest] = []
        groups[digest].append(path)

    matches = []
    for group in groups.values():
        if len(group) > 1:
            matches.append(group)

    return matches


def find_in_size_groups(size_groups):
    """Take files grouped by size and return the sets that are
    truly identical."""
    duplicates = []

    for size, paths in size_groups.items():
        if size <= PARTIAL_SIZE:
            # Small file: one full read is enough
            duplicates.extend(group_by_hash(paths, partial=False))
        else:
            # Big file: quick 64 KB check first, full read only for survivors
            for partial_group in group_by_hash(paths, partial=True):
                duplicates.extend(group_by_hash(partial_group, partial=False))

    return duplicates


def find_duplicates(folder_path, include_hidden=False):
    """Find sets of identical files inside a folder.
    Returns a list of sets, each set being a list of file paths."""
    files = scan_folder(folder_path, include_hidden)
    return find_in_size_groups(group_by_size(files))


if __name__ == "__main__":
    import time

    folder = input("Enter a folder path: ")

    start = time.perf_counter()
    files = scan_folder(folder)
    print(f"Listed {len(files)} files in {time.perf_counter() - start:.1f} s")

    size_groups = group_by_size(files)
    candidate_count = sum(len(p) for p in size_groups.values())
    candidate_mb = sum(s * len(p) for s, p in size_groups.items()) / (1024 * 1024)
    print(f"{candidate_count} files share a size with another file "
        f"({candidate_mb:.0f} MB in total)")

    start = time.perf_counter()
    duplicates = find_in_size_groups(size_groups)
    print(f"Hashing took {time.perf_counter() - start:.1f} s")

    print(f"Found {len(duplicates)} sets of duplicate files")
    for number, group in enumerate(duplicates, start=1):
        print(f"\nSet {number}:")
        for p in group:
            print("   ", p)