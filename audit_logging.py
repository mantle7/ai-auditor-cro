import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


LOG_PATH = Path(__file__).resolve().parent / "output" / "audit_log.jsonl"


def log_audit_event(url, persona, status, report_path=None, error=None):
    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_ist": datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).isoformat(),
        "url": url,
        "persona_id": persona.get("id"),
        "persona_name": persona.get("name"),
        "business_type": persona.get("segment"),
        "status": status,
        "report_path": str(report_path) if report_path else None,
        "error": error,
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(f"[AUDIT_LOG] {json.dumps(event, ensure_ascii=False)}")
