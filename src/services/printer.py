import subprocess
from pathlib import Path


def print_pdf(pdf_path: Path) -> None:
    subprocess.run(
        ["lp", str(pdf_path)],
        check=True,
    )