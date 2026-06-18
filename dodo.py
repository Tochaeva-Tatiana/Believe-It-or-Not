"""Automation tasks for Believe-It-or-Not development."""

from pathlib import Path
import shutil
import subprocess
import sys


PYTHON = sys.executable

PO_DIR = Path("believe/server/po")
POT_FILE = PO_DIR / "believe_server.pot"

DOC_DIR = Path("doc")
DOC_BUILD_DIR = DOC_DIR / "_build"
HTML_DIR = DOC_BUILD_DIR / "html"
HTML_INDEX = HTML_DIR / "index.html"
PACKAGE_DOC_DIR = Path("believe/documentation")
PACKAGE_DOC_INDEX = PACKAGE_DOC_DIR / "index.html"

DIST_DIR = Path("dist")
WHEEL_FILE = DIST_DIR / "believe-0.1.0-py3-none-any.whl"
SDIST_FILE = DIST_DIR / "believe-0.1.0.tar.gz"

LOCALES = (
    "ru_RU",
    "ru_BY",
)


def python_sources() -> list[str]:
    """Return project Python source files."""
    return [
        str(path)
        for path in Path("believe").rglob("*.py")
    ]


def documentation_sources() -> list[str]:
    """Return Sphinx documentation source files."""
    return [
        str(path)
        for path in DOC_DIR.rglob("*.rst")
    ] + [
        str(DOC_DIR / "conf.py"),
    ]


def po_path(locale: str) -> Path:
    """Return PO file path for one locale."""
    return PO_DIR / locale / "LC_MESSAGES" / "believe_server.po"


def mo_path(locale: str) -> Path:
    """Return MO file path for one locale."""
    return PO_DIR / locale / "LC_MESSAGES" / "believe_server.mo"


def po_files() -> list[str]:
    """Return translation source files."""
    return [
        str(po_path(locale))
        for locale in LOCALES
    ]


def mo_files() -> list[str]:
    """Return compiled translation files."""
    return [
        str(mo_path(locale))
        for locale in LOCALES
    ]


def run_command(command: list[str]) -> None:
    """Run one external command."""
    subprocess.run(command, check=True)


def init_or_update_po(locale: str) -> None:
    """Create or update one PO catalog."""
    catalog = po_path(locale)
    catalog.parent.mkdir(parents=True, exist_ok=True)

    if catalog.exists():
        run_command(
            [
                "pybabel",
                "update",
                "-i",
                str(POT_FILE),
                "-d",
                str(PO_DIR),
                "-D",
                "believe_server",
                "-l",
                locale,
            ],
        )
        return

    run_command(
        [
            "pybabel",
            "init",
            "-i",
            str(POT_FILE),
            "-d",
            str(PO_DIR),
            "-D",
            "believe_server",
            "-l",
            locale,
        ],
    )


def copy_documentation() -> None:
    """Copy built HTML documentation into the package."""
    if PACKAGE_DOC_DIR.exists():
        shutil.rmtree(PACKAGE_DOC_DIR)

    shutil.copytree(HTML_DIR, PACKAGE_DOC_DIR)


def remove_path(path: str) -> None:
    """Remove file or directory if it exists."""
    target = Path(path)

    if target.is_dir():
        shutil.rmtree(target)
        return

    if target.exists():
        target.unlink()


def task_i18n_pot() -> dict[str, object]:
    """Extract gettext messages into a POT template."""
    return {
        "actions": [
            (
                "pybabel extract "
                "-F babel.cfg "
                f"-o {POT_FILE} "
                "believe"
            ),
        ],
        "file_dep": [
            "babel.cfg",
            *python_sources(),
        ],
        "targets": [
            str(POT_FILE),
        ],
        "clean": True,
    }


def task_i18n_po() -> dict[str, object]:
    """Create or update PO translation catalogs."""
    return {
        "actions": [
            (init_or_update_po, [locale])
            for locale in LOCALES
        ],
        "file_dep": [
            str(POT_FILE),
        ],
        "targets": po_files(),
        "task_dep": [
            "i18n_pot",
        ],
    }


def task_i18n_mo() -> dict[str, object]:
    """Compile PO translation catalogs into MO files."""
    return {
        "actions": [
            (
                "pybabel compile "
                f"-d {PO_DIR} "
                "-D believe_server"
            ),
        ],
        "file_dep": po_files(),
        "targets": mo_files(),
        "task_dep": [
            "i18n_po",
        ],
        "clean": True,
    }


def task_i18n() -> dict[str, object]:
    """Run all localization tasks."""
    return {
        "actions": [],
        "task_dep": [
            "i18n_pot",
            "i18n_po",
            "i18n_mo",
        ],
    }


def task_html() -> dict[str, object]:
    """Build Sphinx HTML documentation."""
    return {
        "actions": [
            f"sphinx-build -M html {DOC_DIR} {DOC_BUILD_DIR}",
        ],
        "file_dep": [
            *documentation_sources(),
            *python_sources(),
        ],
        "targets": [
            str(HTML_INDEX),
        ],
        "clean": True,
    }


def task_package_docs() -> dict[str, object]:
    """Copy HTML documentation into the package."""
    return {
        "actions": [
            copy_documentation,
        ],
        "file_dep": [
            str(HTML_INDEX),
        ],
        "targets": [
            str(PACKAGE_DOC_INDEX),
        ],
        "task_dep": [
            "html",
        ],
        "clean": [
            (remove_path, [str(PACKAGE_DOC_DIR)]),
        ],
    }


def task_test() -> dict[str, object]:
    """Run unittest test suite."""
    return {
        "actions": [
            f"{PYTHON} -m unittest discover -s tests",
        ],
    }


def task_coverage() -> dict[str, object]:
    """Run tests and create terminal and HTML coverage reports."""
    return {
        "actions": [
            f"{PYTHON} -m coverage erase",
            (
                f"{PYTHON} -m coverage run "
                "-m unittest discover -s tests"
            ),
            f"{PYTHON} -m coverage report -m",
            f"{PYTHON} -m coverage html",
        ],
    }


def task_flake8() -> dict[str, object]:
    """Run flake8 style checks."""
    return {
        "actions": [
            f"{PYTHON} -m flake8 believe tests dodo.py",
        ],
    }


def task_pydocstyle() -> dict[str, object]:
    """Run pydocstyle checks for package modules."""
    return {
        "actions": [
            f"{PYTHON} -m pydocstyle believe",
        ],
    }


def task_check() -> dict[str, object]:
    """Run the main project checks."""
    return {
        "actions": [],
        "task_dep": [
            "test",
            "flake8",
            "pydocstyle",
            "html",
            "i18n_mo",
        ],
    }


def task_wheel() -> dict[str, object]:
    """Build a wheel distribution."""
    return {
        "actions": [
            f"{PYTHON} -m build --wheel",
        ],
        "file_dep": [
            "pyproject.toml",
            *python_sources(),
            *mo_files(),
            str(PACKAGE_DOC_INDEX),
        ],
        "targets": [
            str(WHEEL_FILE),
        ],
        "task_dep": [
            "i18n_mo",
            "package_docs",
        ],
        "clean": True,
    }


def task_sdist() -> dict[str, object]:
    """Build a source distribution."""
    return {
        "actions": [
            f"{PYTHON} -m build --sdist",
        ],
        "file_dep": [
            "pyproject.toml",
            *python_sources(),
            *mo_files(),
            str(PACKAGE_DOC_INDEX),
        ],
        "targets": [
            str(SDIST_FILE),
        ],
        "task_dep": [
            "i18n_mo",
            "package_docs",
        ],
        "clean": True,
    }
