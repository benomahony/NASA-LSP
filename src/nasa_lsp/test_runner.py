"""Test runner that runs pytest with coverage, then mutation tests."""
# ruff: noqa: T201, S607, SIM105

import subprocess
import sys


def main() -> int:
    """Run tests with coverage, then mutation tests if successful."""
    assert sys.version_info >= (3, 13), "Python 3.13+ required"
    assert subprocess.run is not None, "subprocess.run must be available"

    print("Running tests with coverage...")
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "--cov=src/nasa_lsp",
            "--cov-report=term-missing",
            "--cov-report=json",
            "--cov-fail-under=90",
        ],
        check=False,
    )

    if result.returncode != 0:
        return result.returncode

    print("\nRunning mutation tests...")
    result = subprocess.run(["uv", "run", "mutmut", "run"], check=False)

    if result.returncode != 0:
        return result.returncode

    print("\nChecking mutation score...")
    result = subprocess.run(
        ["uv", "run", "mutmut", "results"],
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout
    print(output)

    # Count survived mutations
    survived = 0
    for line in output.split("\n"):
        if "🙁" in line:
            parts = line.split("🙁")
            if len(parts) > 1:
                try:
                    survived = int(parts[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

    if survived > 0:
        print(f"❌ {survived} mutation(s) survived")
        return 1

    print("✅ All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
