"""Sphinx configuration for the CashMachine documentation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the project importable so autodoc can inspect Django modules.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("CASHMACHINE_DB_PATH", str(ROOT / "docs" / "_build_db.sqlite3"))

import django  # noqa: E402

django.setup()


# ---------------------------------------------------------------------------
# Project information
# ---------------------------------------------------------------------------

project = "CashMachine"
author = "CashMachine contributors"
copyright = "2026, CashMachine contributors"
release = "1.0"


# ---------------------------------------------------------------------------
# General configuration
# ---------------------------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
]

language = "ru"

templates_path = ["_templates"]
exclude_patterns: list[str] = []

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"

napoleon_google_docstring = True
napoleon_numpy_docstring = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": (
        "https://docs.djangoproject.com/en/stable/",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
}
# Don't fail the build if intersphinx can't reach docs.djangoproject.com from
# the sandbox — the reference is still useful when links resolve locally.
intersphinx_disabled_reftypes = ["*"]


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

html_theme = "furo"
html_title = "CashMachine · документация"
html_static_path = ["_static"]

# Autodoc reads type hints that reference internal Django classes such as
# ``django.http.request.HttpRequest``. Those live outside the intersphinx
# scope enabled above, so we silence the pedantic cross-reference warnings
# rather than dropping ``-W`` from the Makefile.
suppress_warnings = [
    "autosectionlabel.*",
    "epub.unknown_project_files",
    "ref.class",
    "ref.obj",
    "ref.exc",
    "ref.func",
    "ref.meth",
    "ref.mod",
    "ref.attr",
    "ref.python",
]
