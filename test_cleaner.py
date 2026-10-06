import os

import pytest

import cleaner
from cleaner import choose_keeper, delete_duplicates, delete_selected


@pytest.fixture(autouse=True)
def fake_recycle_bin(monkeypatch):
    """Replace send2trash with a stand-in that just removes the file,
    so tests never touch the real Recycle Bin."""

    def fake_trash(path):
        os.remove(path)

    monkeypatch.setattr(cleaner, "send2trash", fake_trash)


def make_file(folder, name, content=b"same", mtime=None):
    """Create a file, optionally with a chosen 'last modified' time."""
    path = folder / name
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return str(path)


# ---------- choose_keeper ----------

def test_oldest_rule_keeps_the_earliest_modified_file(tmp_path):
    old = make_file(tmp_path, "old.txt", mtime=1_000_000)
    new = make_file(tmp_path, "new.txt", mtime=2_000_000)

    assert choose_keeper([new, old], "oldest") == old


def test_newest_rule_keeps_the_latest_modified_file(tmp_path):
    old = make_file(tmp_path, "old.txt", mtime=1_000_000)
    new = make_file(tmp_path, "new.txt", mtime=2_000_000)

    assert choose_keeper([old, new], "newest") == new


def test_tie_on_date_prefers_the_shorter_path(tmp_path):
    original = make_file(tmp_path, "photo.jpg", mtime=1_000_000)
    copy = make_file(tmp_path, "photo (1).jpg", mtime=1_000_000)

    assert choose_keeper([copy, original], "oldest") == original
    assert choose_keeper([copy, original], "newest") == original


def test_shortest_path_rule(tmp_path):
    short = make_file(tmp_path, "a.txt")
    long = make_file(tmp_path, "a-much-longer-name.txt")

    assert choose_keeper([long, short], "shortest_path") == short


def test_unknown_rule_raises_an_error(tmp_path):
    a = make_file(tmp_path, "a.txt")

    with pytest.raises(ValueError):
        choose_keeper([a], "banana")


def test_keeper_is_none_when_no_file_exists(tmp_path):
    ghosts = [str(tmp_path / "ghost1.txt"), str(tmp_path / "ghost2.txt")]

    assert choose_keeper(ghosts) is None


# ---------- delete_duplicates ----------

def test_dry_run_deletes_nothing(tmp_path):
    keep = make_file(tmp_path, "keep.txt")
    extra = make_file(tmp_path, "extra.txt")

    done, failed = delete_duplicates([keep, extra], keep, dry_run=True)

    assert done == [extra]
    assert failed == []
    assert os.path.exists(keep)
    assert os.path.exists(extra)


def test_real_run_removes_everything_except_the_keeper(tmp_path):
    keep = make_file(tmp_path, "keep.txt")
    copy1 = make_file(tmp_path, "copy1.txt")
    copy2 = make_file(tmp_path, "copy2.txt")

    done, failed = delete_duplicates([keep, copy1, copy2], keep, dry_run=False)

    assert sorted(done) == sorted([copy1, copy2])
    assert failed == []
    assert os.path.exists(keep)
    assert not os.path.exists(copy1)
    assert not os.path.exists(copy2)


def test_missing_keeper_is_refused(tmp_path):
    real = make_file(tmp_path, "real.txt")
    ghost = str(tmp_path / "ghost.txt")

    with pytest.raises(ValueError):
        delete_duplicates([real, ghost], ghost, dry_run=False)

    assert os.path.exists(real)


def test_keeper_outside_the_set_is_refused(tmp_path):
    a = make_file(tmp_path, "a.txt")
    b = make_file(tmp_path, "b.txt")
    outsider = make_file(tmp_path, "outsider.txt")

    with pytest.raises(ValueError):
        delete_duplicates([a, b], outsider, dry_run=False)

    assert os.path.exists(a)
    assert os.path.exists(b)


def test_locked_file_is_reported_not_crashed(tmp_path, monkeypatch):
    keep = make_file(tmp_path, "keep.txt")
    locked = make_file(tmp_path, "locked.txt")

    def failing_trash(path):
        raise PermissionError("file is locked")

    monkeypatch.setattr(cleaner, "send2trash", failing_trash)

    done, failed = delete_duplicates([keep, locked], keep, dry_run=False)

    assert done == []
    assert failed == [(locked, "file is locked")]
    assert os.path.exists(locked)


# ---------- delete_selected ----------

def test_delete_selected_removes_only_the_chosen_files(tmp_path):
    a = make_file(tmp_path, "a.txt")
    b = make_file(tmp_path, "b.txt")
    c = make_file(tmp_path, "c.txt")

    done, failed = delete_selected([a, b, c], [b])

    assert done == [b]
    assert failed == []
    assert os.path.exists(a)
    assert os.path.exists(c)
    assert not os.path.exists(b)


def test_delete_selected_refuses_to_remove_every_copy(tmp_path):
    a = make_file(tmp_path, "a.txt")
    b = make_file(tmp_path, "b.txt")

    with pytest.raises(ValueError):
        delete_selected([a, b], [a, b])

    assert os.path.exists(a)
    assert os.path.exists(b)


def test_delete_selected_never_removes_the_last_surviving_copy(tmp_path):
    survivor = make_file(tmp_path, "survivor.txt")
    ghost = str(tmp_path / "already-gone.txt")

    with pytest.raises(ValueError):
        delete_selected([survivor, ghost], [survivor])

    assert os.path.exists(survivor)


def test_delete_selected_reports_files_not_in_the_set(tmp_path):
    a = make_file(tmp_path, "a.txt")
    b = make_file(tmp_path, "b.txt")
    outsider = make_file(tmp_path, "outsider.txt")

    done, failed = delete_selected([a, b], [a, outsider])

    assert done == [a]
    assert failed == [(outsider, "not part of this set")]
    assert os.path.exists(outsider)