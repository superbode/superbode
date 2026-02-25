#------------------------------------------------------------
#                         __init__.py
#     Exposes the package-level updater entrypoint import.

from .controller import run_update

__all__ = ["run_update"]
