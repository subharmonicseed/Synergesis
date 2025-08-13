from __future__ import annotations

"""SQLite persistence helper for Synergesis patterns.
Creates a single table storing the raw JSON representation of each Pattern.
If the database cannot be initialised (e.g., missing package), the rest of
Synergesis operates in in-memory mode – callers should check `available`.
"""

import os
import json
from datetime import datetime
from typing import Any

try:
    from sqlmodel import SQLModel, Field, create_engine, Session

    DATABASE_URL = os.getenv("SYNERGESIS_DB_URL", "sqlite:///./glyphs.db")
    _engine = create_engine(DATABASE_URL, echo=False)

    class PatternRecord(SQLModel, table=True):
        id: str = Field(primary_key=True)
        timestamp: float
        data: str  # JSON payload of Pattern.to_dict()

    def _init_db() -> None:
        SQLModel.metadata.create_all(_engine)

    _init_db()
    available = True

    def save_pattern(pattern: "Pattern") -> None:  # noqa: F821 – runtime import
        """Upsert a Pattern into the DB."""
        record_dict: dict[str, Any] = pattern.to_dict()  # type: ignore[attr-defined]
        with Session(_engine) as session:
            rec = PatternRecord(id=pattern.id,
                                timestamp=record_dict.get("timestamp", datetime.now().timestamp()),
                                data=json.dumps(record_dict, default=str))
            session.merge(rec)
            session.commit()

except Exception as e:  # pragma: no cover – optional dependency failure
    # sqlmodel or engine init failed – disable persistence, but keep the app running.
    print(f"[DB] Persistence disabled: {e}")
    available = False

    def save_pattern(*_args, **_kwargs):  # type: ignore[override]
        return None
