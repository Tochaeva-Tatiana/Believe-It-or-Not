"""Automation tasks for Believe-It-or-Not development."""

from pathlib import Path
import sys


PYTHON = sys.executable

PO_DIR = Path("believe/server/po")
POT_FILE = PO_DIR / "believe_server.pot"
DOC_DIR = Path("doc")
DOC_BUILD_DIR = DOC_DIR / "_build"
HTML_INDEX = DOC_BUILD_DIR / "html" / "index.html"

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


def po_files() -> list[str]:
    """Return translation source files."""
    return [
        str(PO_DIR / locale / "LC_MESSAGES" / "believe_server.po")
        for locale in LOCALES
    ]


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
    """Update PO translation catalogs from the POT template."""
    actions = [
        (
            "pybabel update "
            f"-i {POT_FILE} "
            f"-d {PO_DIR} "
            "-D believe_server "
            f"-l {locale}"
        )
        for locale in LOCALES
    ]

    return {
        "actions": actions,
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
        "task_dep": [
            "i18n_po",
        ],
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


def task_test() -> dict[str, object]:
    """Run unittest test suite."""
    return {
        "actions": [
            f"{PYTHON} -m unittest discover -s tests",
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
