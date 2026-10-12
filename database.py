"""SQLite data access for legal cases."""
import sqlite3
from contextlib import contextmanager

from models import Case

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    number      TEXT NOT NULL UNIQUE,
    client      TEXT NOT NULL,
    opened_on   TEXT NOT NULL,
    status      TEXT NOT NULL,
    lawyer      TEXT NOT NULL,
    description TEXT
)
"""


class DuplicateCaseError(Exception):
    pass


class CaseRepository:
    def __init__(self, path):
        self.path = path
        with self._connect() as conn:
            conn.execute(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _to_case(row):
        return Case(**dict(row)) if row else None

    def add(self, case):
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO cases (number, client, opened_on, status, lawyer, description) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (case.number, case.client, case.opened_on, case.status, case.lawyer, case.description),
                )
                case.id = cur.lastrowid
                return case
        except sqlite3.IntegrityError:
            raise DuplicateCaseError(f"A case with number {case.number} already exists.")

    def update(self, case):
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE cases SET number=?, client=?, opened_on=?, status=?, lawyer=?, description=? "
                    "WHERE id=?",
                    (case.number, case.client, case.opened_on, case.status, case.lawyer,
                     case.description, case.id),
                )
        except sqlite3.IntegrityError:
            raise DuplicateCaseError(f"A case with number {case.number} already exists.")

    def get(self, case_id):
        with self._connect() as conn:
            return self._to_case(conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone())

    def delete(self, case_id):
        with self._connect() as conn:
            return conn.execute("DELETE FROM cases WHERE id=?", (case_id,)).rowcount > 0

    def search(self, text="", status="", lawyer=""):
        """Filter cases. All filters are optional and combined with AND."""
        query, params = "SELECT * FROM cases WHERE 1=1", []
        if text:
            query += " AND (number LIKE ? OR client LIKE ? OR description LIKE ?)"
            params += [f"%{text}%"] * 3
        if status:
            query += " AND status = ?"
            params.append(status)
        if lawyer:
            query += " AND lawyer = ?"
            params.append(lawyer)
        query += " ORDER BY opened_on DESC, id DESC"
        with self._connect() as conn:
            return [self._to_case(r) for r in conn.execute(query, params)]

    def lawyers(self):
        with self._connect() as conn:
            return [r[0] for r in conn.execute("SELECT DISTINCT lawyer FROM cases ORDER BY lawyer")]

    def count_by(self, column):
        if column not in ("status", "lawyer"):
            raise ValueError("Can only group by status or lawyer")
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {column}, COUNT(*) FROM cases GROUP BY {column} ORDER BY COUNT(*) DESC"
            )
            return dict(rows.fetchall())
