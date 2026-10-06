import os

from engine import PARTIAL_SIZE, find_duplicates, scan_folder


def make_file(folder, name, content=b"hello"):
    """Create a file (and any missing subfolders) inside a test folder."""
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def names(duplicates):
    """Turn the results into sorted file names, so tests are easy to read."""
    return sorted(
        sorted(os.path.basename(p) for p in group) for group in duplicates
    )


def test_finds_identical_files_with_different_names(tmp_path):
    make_file(tmp_path, "report.txt", b"same content")
    make_file(tmp_path, "report (1).txt", b"same content")

    result = find_duplicates(str(tmp_path))

    assert names(result) == [["report (1).txt", "report.txt"]]


def test_same_name_different_content_is_not_a_duplicate(tmp_path):
    make_file(tmp_path, "one/report.txt", b"version one")
    make_file(tmp_path, "two/report.txt", b"version two")

    assert find_duplicates(str(tmp_path)) == []


def test_same_size_different_content_is_not_a_duplicate(tmp_path):
    make_file(tmp_path, "a.txt", b"aaaa")
    make_file(tmp_path, "b.txt", b"bbbb")

    assert find_duplicates(str(tmp_path)) == []


def test_finds_duplicates_in_subfolders(tmp_path):
    make_file(tmp_path, "top.txt", b"shared")
    make_file(tmp_path, "deep/down/copy.txt", b"shared")

    result = find_duplicates(str(tmp_path))

    assert names(result) == [["copy.txt", "top.txt"]]


def test_big_identical_files_are_found(tmp_path):
    content = b"x" * (PARTIAL_SIZE * 3)
    make_file(tmp_path, "big1.bin", content)
    make_file(tmp_path, "big2.bin", content)

    result = find_duplicates(str(tmp_path))

    assert names(result) == [["big1.bin", "big2.bin"]]


def test_big_files_that_differ_after_first_64kb_are_not_duplicates(tmp_path):
    start = b"x" * (PARTIAL_SIZE + 10)
    make_file(tmp_path, "big1.bin", start + b"A")
    make_file(tmp_path, "big2.bin", start + b"B")

    assert find_duplicates(str(tmp_path)) == []


def test_empty_files_are_ignored(tmp_path):
    make_file(tmp_path, "empty1.txt", b"")
    make_file(tmp_path, "empty2.txt", b"")

    assert find_duplicates(str(tmp_path)) == []


def test_office_lock_files_are_skipped(tmp_path):
    make_file(tmp_path, "~$slides.pptx", b"lock data")
    make_file(tmp_path, "~$notes.docx", b"lock data")

    assert find_duplicates(str(tmp_path)) == []
    assert len(find_duplicates(str(tmp_path), include_hidden=True)) == 1


def test_names_with_accents_and_other_alphabets(tmp_path):
    make_file(tmp_path, "café.txt", b"unicode test")
    make_file(tmp_path, "резюме.txt", b"unicode test")

    result = find_duplicates(str(tmp_path))

    assert len(result) == 1
    assert len(result[0]) == 2


def test_scanning_a_missing_folder_does_not_crash(tmp_path):
    missing = str(tmp_path / "does-not-exist")

    assert scan_folder(missing) == []
    assert find_duplicates(missing) == []