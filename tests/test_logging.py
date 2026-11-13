# tests/test_logging.py
import json, logging
from app.core.logging import JSONFormatter

def test_json_formatter_inclui_extras():
    fmt = JSONFormatter()
    record = logging.LogRecord("sync", logging.INFO, "sync.py", 10,
                               "snapshot_saved", None, None)
    record.institution = "Inter"
    payload = json.loads(fmt.format(record))
    assert payload["event"] == "snapshot_saved"
    assert payload["institution"] == "Inter"
