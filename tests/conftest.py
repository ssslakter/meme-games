import os, tempfile
from pathlib import Path

# every test module shares one throwaway database, set before meme_games is imported
os.environ.setdefault('DB_PATH', str(Path(tempfile.mkdtemp()) / 'test.db'))
