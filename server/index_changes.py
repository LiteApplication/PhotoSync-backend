from .utils import Singleton
from .configuration import ConfigFile
import time
import sqlite3


class ChangeDB(metaclass=Singleton):
    """
    The database contains a table with the following fields: (primary key: id)
    - id: the id of the change
    - user: user affected by the change
    - date : the date of the change

    Another table is used to store the affected files: (no primary key)
    - id: the id of the change
    - file: the file affected by the change (it's id in the index)

    The last table is used to store the additional users affected by the change: (no primary key)
    - id: the id of the change
    - user: the user affected by the change

    The tables are created if they don't exist.
    """

    def __init__(self) -> None:
        self.db = sqlite3.connect(
            ConfigFile().history_database, check_same_thread=False
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS changes (id INTEGER PRIMARY KEY AUTOINCREMENT, user VARCHAR(16), date INTEGER)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS files (id INTEGER, file VARCHAR(12))"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER, user VARCHAR(16))"
        )
        self.db.commit()

    def add_change(self, file_infos: dict) -> None:
        self._add_change(file_infos["id"], file_infos["owner"], file_infos["rights"])

    def _add_change(self, file_id: str, user: str, users: list) -> None:
        """
        Add a change to the database.
        """
        cursor = self.db.cursor()
        date = int(time.time())
        cursor.execute("INSERT INTO changes (user, date) VALUES (?, ?)", (user, date))
        change_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO files (id, file) VALUES (?, ?)", (change_id, file_id)
        )
        for user in users:
            cursor.execute(
                "INSERT INTO users (id, user) VALUES (?, ?)", (change_id, user)
            )
        self.db.commit()

    def get_changes(self, user: str, since: int) -> list:
        """
        Return all the (unique) affected files id.
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT DISTINCT file FROM files WHERE id IN (SELECT id FROM users WHERE user = ? AND date > ?)",
            (user, since),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_changes_from_id(self, user: str, last_id: int) -> list:
        """
        Return all the changes that happened after the given id.
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT DISTINCT file FROM files WHERE id IN (SELECT id FROM changes WHERE id > ? AND user = ?)",
            (last_id, user),
        )
        return cursor.fetchall()

    def get_last_id(self, user: str) -> int:
        """
        Return the id of the last change for the given user.
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT MAX(id) FROM changes WHERE user = ?", (user,))
        return cursor.fetchone()[0]
