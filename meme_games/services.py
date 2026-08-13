"""Composition root. Import this before anything that resolves a service, so the
database exists by the time DI builds a repo. Import order is enforced by the
import graph, not by statement order in main.py."""
import os
from pathlib import Path
from .core import DI, init_db

__all__ = ['db', 'data_dir']

db_path = Path(os.environ.get('DB_PATH', 'data/data.db'))
data_dir = db_path.parent

db = init_db(str(db_path))
DI.register_instance(db)
