"""Filesystem anchors — the single place that knows default locations.

Old scratch scripts hardcoded install paths in several files (and two of them
still pointed at a removed `C:\Program Files (x86)` install). Everything here
resolves through this module so the paths can be overridden or relocated in
one place.
"""

import os

DEFAULT_INSTALL = r'A:\samilpo-res\Samilpo 2.0'


def default_cod(install=None):
    """Path of the primary code table (889F.cod) under an install directory."""
    return os.path.join(install or DEFAULT_INSTALL, '889F.cod')


def default_songs(install=None):
    """Directory holding the .smc corpus of an install."""
    return os.path.join(install or DEFAULT_INSTALL, '8000Songs')
