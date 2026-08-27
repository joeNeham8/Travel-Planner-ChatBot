import logging
import os
import sys
from datetime import datetime

try:
    from from_root import from_root
    _ROOT = from_root()
except Exception:
    # Fall back gracefully (e.g. inside some container/test environments)
    _ROOT = os.getcwd()

LOG_DIR = os.path.join(_ROOT, "log")
os.makedirs(LOG_DIR, exist_ok=True)  # makedirs on the DIRECTORY, not the file

LOG_FILE_NAME = f"{datetime.now().strftime('%Y_%m_%d')}.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

_logger = logging.getLogger("cbot")
_logger.setLevel(logging.INFO)

if not _logger.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    )

    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    _logger.addHandler(stream_handler)

# Keep `logging` importable the same way the rest of the codebase expects
# (`from src.agentic.logger import logging`), but make it OUR configured
# logger object so log calls actually go through the handlers above.
logging = _logger
