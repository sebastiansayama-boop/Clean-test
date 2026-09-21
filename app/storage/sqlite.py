import sqlite3
from pathlib import Path

from ..models import Evidence, Operation


class SQLiteStore:
    def __init__(self, path="router.db"):
        self.path = Path(path)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        db = self._connect()
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS operations("
                "operation_id TEXT PRIMARY KEY,payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS evidence("
                "evidence_id TEXT PRIMARY KEY,operation_id TEXT NOT NULL,payload TEXT NOT NULL)"
            )
            db.commit()
        finally:
            db.close()

    def save_operation(self, op):
        db = self._connect()
        try:
            db.execute(
                "INSERT OR REPLACE INTO operations VALUES(?,?)",
                (op.operation_id, op.model_dump_json()),
            )
            db.commit()
        finally:
            db.close()

    def get_operation(self, oid):
        db = self._connect()
        try:
            row = db.execute(
                "SELECT payload FROM operations WHERE operation_id=?",
                (oid,),
            ).fetchone()
        finally:
            db.close()
        return Operation.model_validate_json(row[0]) if row else None

    def add_evidence(self, e):
        db = self._connect()
        try:
            db.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?)",
                (e.evidence_id, e.operation_id, e.model_dump_json()),
            )
            db.commit()
        finally:
            db.close()

    def list_evidence(self, oid):
        db = self._connect()
        try:
            rows = db.execute(
                "SELECT payload FROM evidence WHERE operation_id=? ORDER BY rowid",
                (oid,),
            ).fetchall()
        finally:
            db.close()
        return [Evidence.model_validate_json(r[0]) for r in rows]
