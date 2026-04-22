from contextlib import contextmanager

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor

from backend.app.core.config import settings


class DatabaseUnavailableError(RuntimeError):
    pass


def get_connection():
    try:
        return psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connect_timeout=5,
            application_name="conciliador_xml_web",
        )
    except OperationalError as exc:
        raise DatabaseUnavailableError(
            f"No fue posible conectar con PostgreSQL en {settings.db_host}:{settings.db_port}."
        ) from exc


@contextmanager
def get_cursor(dictionary: bool = False):
    connection = get_connection()
    try:
        cursor_factory = RealDictCursor if dictionary else None
        cursor = connection.cursor(cursor_factory=cursor_factory)
        try:
            yield connection, cursor
        finally:
            cursor.close()
    finally:
        connection.close()
