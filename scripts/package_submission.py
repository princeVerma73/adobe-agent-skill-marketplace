#!/usr/bin/env python3
"""
Packaging and Validation Script for Adobe Agent Marketplace Submission.
Creates submission.zip with POSIX paths, strict file filtering, and validation.
"""
import shutil
import zipfile
from pathlib import Path


def clean_bytecode(root_dir: Path) -> int:
    """Recursively delete all __pycache__ folders and *.pyc/*.pyo files."""
    count = 0
    for p in list(root_dir.rglob("__pycache__")):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            count += 1
    for p in list(root_dir.rglob("*.pyc")):
        if p.is_file():
            p.unlink(missing_ok=True)
            count += 1
    for p in list(root_dir.rglob("*.pyo")):
        if p.is_file():
            p.unlink(missing_ok=True)
            count += 1
    return count


def package_submission(root_dir: Path, output_zip: Path) -> None:
    """Package the submission into a zipfile with POSIX paths and strict inclusions."""
    top_level_files = [
        "marketplace.json",
        "README.md",
        "pytest.ini",
        "requirements.txt",
    ]

    include_dirs = [
        "examples",
        "skills",
        "src",
        "tests",
    ]

    excluded_patterns = {
        "__pycache__",
        ".venv",
        "env",
        "virtualenv",
        ".git",
        ".github",
        ".pytest_cache",
    }

    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Add top-level files
        for fname in top_level_files:
            file_path = root_dir / fname
            if file_path.exists() and file_path.is_file():
                zf.write(file_path, arcname=fname)
            else:
                raise FileNotFoundError(f"Required top-level file missing: {fname}")

        # 2. Add directories recursively
        for dir_name in include_dirs:
            dir_path = root_dir / dir_name
            if not dir_path.exists() or not dir_path.is_dir():
                raise FileNotFoundError(f"Required directory missing: {dir_name}")

            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                parts = file_path.relative_to(root_dir).parts

                # Exclude unwanted directories / files
                if any(any(part.startswith(exc) or part == exc for exc in excluded_patterns) for part in parts):
                    continue

                # Skip compiled bytecode or temp files
                if file_path.suffix in {".pyc", ".pyo"}:
                    continue

                # POSIX path formatting
                rel_posix = file_path.relative_to(root_dir).as_posix()
                zf.write(file_path, arcname=rel_posix)


def validate_submission(output_zip: Path) -> dict:
    """Validate archive integrity, paths, inclusions, and exclusions."""
    assert output_zip.exists(), f"Archive {output_zip} does not exist!"

    with zipfile.ZipFile(output_zip, "r") as zf:
        namelist = zf.namelist()

        # 1. Verify POSIX path separators (no backslashes)
        backslash_entries = [name for name in namelist if "\\" in name]
        assert len(backslash_entries) == 0, f"Found backslashes in zip: {backslash_entries}"

        # 2. Check required folders and files
        tests_entries = [name for name in namelist if name.startswith("tests/")]
        examples_entries = [name for name in namelist if name.startswith("examples/")]
        skills_entries = [name for name in namelist if name.startswith("skills/")]
        src_entries = [name for name in namelist if name.startswith("src/")]

        assert len(tests_entries) > 0, "No 'tests/' entries found in archive!"
        assert len(examples_entries) > 0, "No 'examples/' entries found in archive!"
        assert len(skills_entries) > 0, "No 'skills/' entries found in archive!"
        assert len(src_entries) > 0, "No 'src/' entries found in archive!"
        assert "pytest.ini" in namelist, "'pytest.ini' missing from archive!"
        assert "marketplace.json" in namelist, "'marketplace.json' missing from archive!"
        assert "README.md" in namelist, "'README.md' missing from archive!"
        assert "requirements.txt" in namelist, "'requirements.txt' missing from archive!"

        # 3. Check exclusions
        pycache_entries = [name for name in namelist if "__pycache__" in name or name.endswith(".pyc")]
        venv_entries = [name for name in namelist if any(v in name for v in [".venv", "env/", "virtualenv/"])]
        git_entries = [name for name in namelist if ".git" in name]
        pytest_cache_entries = [name for name in namelist if ".pytest_cache" in name]
        root_temp_json = [
            name for name in namelist
            if "/" not in name and name.endswith(".json") and name != "marketplace.json"
        ]

        assert len(pycache_entries) == 0, f"__pycache__ found in archive: {pycache_entries}"
        assert len(venv_entries) == 0, f".venv/env found in archive: {venv_entries}"
        assert len(git_entries) == 0, f".git found in archive: {git_entries}"
        assert len(pytest_cache_entries) == 0, f".pytest_cache found in archive: {pytest_cache_entries}"
        assert len(root_temp_json) == 0, f"Root temp json files found in archive: {root_temp_json}"

    # 4. Check final archive size (< 50 MB)
    size_bytes = output_zip.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    assert size_mb < 50.0, f"Archive size ({size_mb:.2f} MB) exceeds 50 MB limit!"

    return {
        "total_files": len(namelist),
        "tests_count": len(tests_entries),
        "examples_count": len(examples_entries),
        "skills_count": len(skills_entries),
        "src_count": len(src_entries),
        "size_mb": size_mb,
        "backslash_count": len(backslash_entries),
        "git_count": len(git_entries),
        "pycache_count": len(pycache_entries),
        "venv_count": len(venv_entries),
        "pytest_cache_count": len(pytest_cache_entries),
    }


def main():
    root_dir = Path(__file__).resolve().parent.parent
    output_zip = root_dir / "submission.zip"

    print(f"Project root: {root_dir}")
    print("Step 2: Cleaning bytecode...")
    cleaned = clean_bytecode(root_dir)
    print(f"Cleaned {cleaned} bytecode/cache items.")

    print("Step 3: Creating submission.zip with POSIX paths...")
    package_submission(root_dir, output_zip)
    print(f"Created {output_zip}")

    print("Step 4: Validating archive...")
    stats = validate_submission(output_zip)
    print("Validation SUCCESSFUL!")
    print(f"  - Total files in archive: {stats['total_files']}")
    print(f"  - 'tests/' files: {stats['tests_count']}")
    print(f"  - 'examples/' files: {stats['examples_count']}")
    print(f"  - 'skills/' files: {stats['skills_count']}")
    print(f"  - 'src/' files: {stats['src_count']}")
    print(f"  - Backslash entries: {stats['backslash_count']}")
    print(f"  - Git entries: {stats['git_count']}")
    print(f"  - Pycache entries: {stats['pycache_count']}")
    print(f"  - Venv entries: {stats['venv_count']}")
    print(f"  - Pytest cache entries: {stats['pytest_cache_count']}")
    print(f"  - Archive size: {stats['size_mb']:.3f} MB")


if __name__ == "__main__":
    main()
