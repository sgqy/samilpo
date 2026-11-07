"""Filesystem anchors — resolving the Samilpo install directory.

The package carries no machine-specific path. The install directory comes
from, in falling priority:

  1. explicit CLI options (``--install-dir`` / ``--cod``, resolved by the
     caller),
  2. the ``SAMILPO_INSTALL`` environment variable.

With neither there is no usable default: callers must report what is missing
instead of guessing at a location or silently degrading text decoding.
"""

import os

INSTALL_ENV = 'SAMILPO_INSTALL'


def resolve_install(explicit=None):
    """Install directory from an explicit argument or the environment;
    ``None`` when neither is available."""
    if explicit:
        return explicit
    return os.environ.get(INSTALL_ENV) or None


def cod_path(install):
    """Path of the primary code table (889F.cod) under an install directory."""
    return os.path.join(install, '889F.cod')


def songs_dir(install):
    """Directory holding the .smc corpus of an install."""
    return os.path.join(install, '8000Songs')
