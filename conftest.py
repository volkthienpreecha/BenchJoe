import shutil
import tempfile
from pathlib import Path

import pytest

_LOCAL_TMP = Path(__file__).parent / ".tmp"


@pytest.fixture
def tmp_path():
    """
    Drop-in replacement for pytest's tmp_path that roots under the project
    directory instead of the Windows system temp folder (which can have
    permission issues).
    """
    _LOCAL_TMP.mkdir(exist_ok=True)
    d = Path(tempfile.mkdtemp(dir=_LOCAL_TMP))
    yield d
    shutil.rmtree(d, ignore_errors=True)
