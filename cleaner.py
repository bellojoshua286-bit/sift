import os

from send2trash import send2trash

KEEP_RULES = ["oldest", "newest", "shortest_path"]


def choose_keeper(group, rule="oldest"):
    """Pick which file in a duplicate set to keep.
    Returns the path to keep, or None if no file exists anymore."""
    existing = [p for p in group if os.path.exists(p)]
    if not existing:
        return None

    if rule == "oldest":
        return min(existing, key=lambda p: (os.path.getmtime(p), len(p)))
    if rule == "newest":
        return max(existing, key=lambda p: (os.path.getmtime(p), -len(p)))
    if rule == "shortest_path":
        return min(existing, key=len)

    raise ValueError(f"Unknown rule: {rule}")


def delete_duplicates(group, keeper, dry_run=True):
    """Remove every file in the group except the keeper.
    dry_run=True only reports what would happen.
    Returns two lists: done (paths) and failed (path, reason)."""
    if keeper is None or keeper not in group or not os.path.exists(keeper):
        raise ValueError("The file to keep must exist and be part of the set")

    done = []
    failed = []

    for path in group:
        if path == keeper:
            continue

        if not os.path.exists(path):
            failed.append((path, "file not found"))
            continue

        if dry_run:
            done.append(path)
            continue

        try:
            send2trash(os.path.abspath(path))
            done.append(path)
        except OSError as error:
            failed.append((path, str(error)))

    return done, failed


def delete_selected(group, selected):
    """Move the chosen files of one duplicate set to the Recycle Bin.
    Refuses if that would remove every remaining copy in the set.
    Returns two lists: done (paths) and failed (path, reason)."""
    remaining = [p for p in group if p not in selected and os.path.exists(p)]
    if not remaining:
        raise ValueError("At least one copy of each set must be kept")

    done = []
    failed = []

    for path in selected:
        if path not in group:
            failed.append((path, "not part of this set"))
            continue

        if not os.path.exists(path):
            failed.append((path, "file not found"))
            continue

        try:
            send2trash(os.path.abspath(path))
            done.append(path)
        except OSError as error:
            failed.append((path, str(error)))

    return done, failed


if __name__ == "__main__":
    from engine import find_duplicates

    folder = input("Enter a folder path: ")
    sets = find_duplicates(folder)

    if not sets:
        print("No duplicates found")
        raise SystemExit

    plan = []
    for number, group in enumerate(sets, start=1):
        keeper = choose_keeper(group, "oldest")
        to_remove, _ = delete_duplicates(group, keeper, dry_run=True)
        plan.append((group, keeper))

        print(f"\nSet {number}: keeping {os.path.basename(keeper)}")
        for p in to_remove:
            print("    will remove", p)

    answer = input("\nMove these files to the Recycle Bin? (yes/no): ")
    if answer.strip().lower() != "yes":
        print("Cancelled. Nothing was deleted.")
        raise SystemExit

    removed = 0
    for group, keeper in plan:
        done, failed = delete_duplicates(group, keeper, dry_run=False)
        removed += len(done)
        for p, reason in failed:
            print("    problem:", p, "-", reason)

    print(f"Done. {removed} files moved to the Recycle Bin.")