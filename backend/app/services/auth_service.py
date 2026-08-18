from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status

from backend.app.core.config import settings
from backend.app.db import get_cursor
from backend.app.models.schemas import AuthUser, LoginResponse, UserActivityItem, UserSummary

logger = logging.getLogger(__name__)

ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
ACTION_LOGIN_FAILURE = "LOGIN_FAILURE"
ACTION_LOGOUT = "LOGOUT"
ACTION_VIEW_RECONCILIATION = "VIEW_RECONCILIATION"
ACTION_MISS_RECONCILIATION = "MISS_RECONCILIATION"
ACTION_UPLOAD_FILE = "UPLOAD_FILE"
ACTION_SCAN_INPUT_FOLDER = "SCAN_INPUT_FOLDER"
ACTION_CREATE_USER = "CREATE_USER"
ACTION_UPDATE_USER = "UPDATE_USER"

PASSWORD_ITERATIONS = 390_000


@dataclass
class SessionContext:
    session_id: int
    user: AuthUser
    token_hash: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _normalize_full_name(full_name: str) -> str:
    return " ".join(full_name.strip().split())


def _password_to_hash(password: str, salt: str) -> str:
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return derived_key.hex()


def hash_password(password: str) -> tuple[str, str]:
    password = password.strip()
    if len(password) < 8:
        raise ValueError("La contrasena debe tener al menos 8 caracteres.")
    salt = secrets.token_hex(16)
    return _password_to_hash(password, salt), salt


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    candidate = _password_to_hash(password.strip(), stored_salt)
    return hmac.compare_digest(candidate, stored_hash)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _request_ip(request: Request | None) -> str | None:
    if request is None:
        return None

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _request_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    return request.headers.get("user-agent")


def _row_to_user(row: dict[str, Any]) -> AuthUser:
    return AuthUser(
        id=int(row["id"]),
        username=str(row["username"]),
        full_name=str(row["full_name"]),
        is_admin=bool(row["is_admin"]),
        is_active=bool(row["is_active"]),
        last_login_at=row.get("last_login_at"),
        created_at=row["created_at"],
    )


def _log_access_event(
    *,
    action: str,
    request: Request | None,
    user_id: int | None = None,
    username_snapshot: str = "desconocido",
    target_nit: str | None = None,
    target_factura: str | None = None,
    detail: str | None = None,
) -> None:
    with get_cursor() as (connection, cursor):
        cursor.execute(
            """
            INSERT INTO app_user_access_logs
            (
                user_id,
                username_snapshot,
                action,
                target_nit,
                target_factura,
                detail,
                ip_address,
                user_agent
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                username_snapshot,
                action,
                target_nit,
                target_factura,
                detail,
                _request_ip(request),
                _request_user_agent(request),
            ),
        )
        connection.commit()


def ensure_auth_schema() -> None:
    with get_cursor() as (connection, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id BIGSERIAL PRIMARY KEY,
                username VARCHAR(80) NOT NULL UNIQUE,
                full_name VARCHAR(120) NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                last_login_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_user_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked_at TIMESTAMPTZ NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_app_user_sessions_user
            ON app_user_sessions(user_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_app_user_sessions_token
            ON app_user_sessions(token_hash)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_user_access_logs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NULL REFERENCES app_users(id) ON DELETE SET NULL,
                username_snapshot VARCHAR(80) NOT NULL,
                action VARCHAR(80) NOT NULL,
                target_nit VARCHAR(32) NULL,
                target_factura VARCHAR(120) NULL,
                detail TEXT NULL,
                ip_address VARCHAR(64) NULL,
                user_agent TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_app_user_access_logs_user_created
            ON app_user_access_logs(user_id, created_at DESC)
            """
        )
        connection.commit()


def ensure_default_admin_user() -> None:
    with get_cursor(dictionary=True) as (connection, cursor):
        cursor.execute("SELECT COUNT(*)::int AS total FROM app_users")
        row = cursor.fetchone()
        if row and int(row["total"]) > 0:
            return

        password_hash, password_salt = hash_password(settings.auth_default_admin_password)
        cursor.execute(
            """
            INSERT INTO app_users
            (
                username,
                full_name,
                password_hash,
                password_salt,
                is_admin,
                is_active
            )
            VALUES (%s, %s, %s, %s, TRUE, TRUE)
            """,
            (
                _normalize_username(settings.auth_default_admin_username),
                _normalize_full_name(settings.auth_default_admin_name),
                password_hash,
                password_salt,
            ),
        )
        connection.commit()

    logger.warning(
        "Usuario administrador inicial creado: %s. Cambia la contrasena despues del primer ingreso.",
        settings.auth_default_admin_username,
    )


def initialize_auth_system() -> None:
    ensure_auth_schema()
    ensure_default_admin_user()


def create_user(
    *,
    username: str,
    full_name: str,
    password: str,
    is_admin: bool,
    is_active: bool,
) -> AuthUser:
    normalized_username = _normalize_username(username)
    normalized_name = _normalize_full_name(full_name)
    if not normalized_username:
        raise ValueError("Debes indicar un nombre de usuario.")
    if not normalized_name:
        raise ValueError("Debes indicar el nombre completo del usuario.")

    password_hash, password_salt = hash_password(password)

    with get_cursor(dictionary=True) as (connection, cursor):
        cursor.execute("SELECT 1 FROM app_users WHERE username = %s", (normalized_username,))
        if cursor.fetchone() is not None:
            raise ValueError("Ya existe un usuario con ese nombre.")

        cursor.execute(
            """
            INSERT INTO app_users
            (
                username,
                full_name,
                password_hash,
                password_salt,
                is_admin,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, username, full_name, is_admin, is_active, last_login_at, created_at
            """,
            (
                normalized_username,
                normalized_name,
                password_hash,
                password_salt,
                is_admin,
                is_active,
            ),
        )
        row = cursor.fetchone()
        connection.commit()

    return _row_to_user(row)


def _active_admin_count(exclude_user_id: int | None = None) -> int:
    with get_cursor(dictionary=True) as (_, cursor):
        if exclude_user_id is None:
            cursor.execute(
                """
                SELECT COUNT(*)::int AS total
                FROM app_users
                WHERE is_admin = TRUE
                  AND is_active = TRUE
                """
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*)::int AS total
                FROM app_users
                WHERE is_admin = TRUE
                  AND is_active = TRUE
                  AND id <> %s
                """,
                (exclude_user_id,),
            )
        row = cursor.fetchone()
    return int(row["total"])


def update_user(
    user_id: int,
    *,
    full_name: str | None = None,
    password: str | None = None,
    is_admin: bool | None = None,
    is_active: bool | None = None,
) -> AuthUser:
    with get_cursor(dictionary=True) as (connection, cursor):
        cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
        existing = cursor.fetchone()
        if existing is None:
            raise ValueError("El usuario indicado no existe.")

        target_is_admin = bool(existing["is_admin"]) if is_admin is None else is_admin
        target_is_active = bool(existing["is_active"]) if is_active is None else is_active
        if bool(existing["is_admin"]) and bool(existing["is_active"]) and (not target_is_admin or not target_is_active):
            if _active_admin_count(exclude_user_id=user_id) == 0:
                raise ValueError("Debe existir al menos un administrador activo.")

        normalized_name = _normalize_full_name(full_name) if full_name is not None else str(existing["full_name"])
        if not normalized_name:
            raise ValueError("El nombre completo no puede quedar vacio.")

        password_hash = str(existing["password_hash"])
        password_salt = str(existing["password_salt"])
        if password is not None and password.strip():
            password_hash, password_salt = hash_password(password)

        cursor.execute(
            """
            UPDATE app_users
            SET full_name = %s,
                password_hash = %s,
                password_salt = %s,
                is_admin = %s,
                is_active = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, username, full_name, is_admin, is_active, last_login_at, created_at
            """,
            (
                normalized_name,
                password_hash,
                password_salt,
                target_is_admin,
                target_is_active,
                user_id,
            ),
        )
        updated = cursor.fetchone()

        if not target_is_active:
            cursor.execute(
                """
                UPDATE app_user_sessions
                SET revoked_at = NOW()
                WHERE user_id = %s
                  AND revoked_at IS NULL
                """,
                (user_id,),
            )

        connection.commit()

    return _row_to_user(updated)


def list_users_with_stats() -> list[UserSummary]:
    with get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.is_admin,
                u.is_active,
                u.last_login_at,
                u.created_at,
                MAX(l.created_at) AS last_activity_at,
                COALESCE(SUM(CASE WHEN l.action = %s THEN 1 ELSE 0 END), 0)::int AS total_consultas,
                COALESCE(SUM(CASE WHEN l.action IN (%s, %s) THEN 1 ELSE 0 END), 0)::int AS total_ingestas,
                COALESCE(COUNT(l.id), 0)::int AS total_eventos
            FROM app_users u
            LEFT JOIN app_user_access_logs l
              ON l.user_id = u.id
            GROUP BY u.id
            ORDER BY u.username ASC
            """,
            (
                ACTION_VIEW_RECONCILIATION,
                ACTION_UPLOAD_FILE,
                ACTION_SCAN_INPUT_FOLDER,
            ),
        )
        rows = cursor.fetchall()

    return [UserSummary(**row) for row in rows]


def list_user_activity(user_id: int, limit: int = 50) -> list[UserActivityItem]:
    with get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                id,
                action,
                target_nit,
                target_factura,
                detail,
                ip_address,
                user_agent,
                created_at
            FROM app_user_access_logs
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()

    return [UserActivityItem(**row) for row in rows]


def authenticate_user(username: str, password: str, request: Request) -> LoginResponse:
    normalized_username = _normalize_username(username)
    with get_cursor(dictionary=True) as (connection, cursor):
        cursor.execute("SELECT * FROM app_users WHERE username = %s", (normalized_username,))
        row = cursor.fetchone()

        if row is None or not verify_password(password, str(row["password_hash"]), str(row["password_salt"])):
            connection.commit()
            _log_access_event(
                action=ACTION_LOGIN_FAILURE,
                request=request,
                username_snapshot=normalized_username or "desconocido",
                detail="Credenciales invalidas",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contrasena invalidos.")

        if not bool(row["is_active"]):
            connection.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario se encuentra inactivo.")

        expires_at = _utc_now() + timedelta(hours=max(settings.auth_session_hours, 1))
        session_token = secrets.token_urlsafe(32)
        token_hash = _hash_session_token(session_token)

        cursor.execute(
            """
            UPDATE app_users
            SET last_login_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, username, full_name, is_admin, is_active, last_login_at, created_at
            """,
            (row["id"],),
        )
        updated_user = cursor.fetchone()

        cursor.execute(
            """
            INSERT INTO app_user_sessions
            (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (row["id"], token_hash, expires_at),
        )
        connection.commit()

    user = _row_to_user(updated_user)
    _log_access_event(
        action=ACTION_LOGIN_SUCCESS,
        request=request,
        user_id=user.id,
        username_snapshot=user.username,
    )
    return LoginResponse(token=session_token, expires_at=expires_at, user=user)


def get_session_context(token: str) -> SessionContext | None:
    token_hash = _hash_session_token(token)
    with get_cursor(dictionary=True) as (connection, cursor):
        cursor.execute(
            """
            SELECT
                s.id AS session_id,
                s.token_hash,
                u.id,
                u.username,
                u.full_name,
                u.is_admin,
                u.is_active,
                u.last_login_at,
                u.created_at
            FROM app_user_sessions s
            INNER JOIN app_users u
                ON u.id = s.user_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        if row is None or not bool(row["is_active"]):
            connection.commit()
            return None

        cursor.execute(
            """
            UPDATE app_user_sessions
            SET last_seen_at = NOW()
            WHERE id = %s
            """,
            (row["session_id"],),
        )
        connection.commit()

    user = _row_to_user(row)
    return SessionContext(session_id=int(row["session_id"]), user=user, token_hash=str(row["token_hash"]))


def revoke_session(session: SessionContext, request: Request | None = None) -> None:
    with get_cursor() as (connection, cursor):
        cursor.execute(
            """
            UPDATE app_user_sessions
            SET revoked_at = NOW()
            WHERE id = %s
              AND revoked_at IS NULL
            """,
            (session.session_id,),
        )
        connection.commit()

    _log_access_event(
        action=ACTION_LOGOUT,
        request=request,
        user_id=session.user.id,
        username_snapshot=session.user.username,
    )


def log_user_action(
    session: SessionContext,
    *,
    action: str,
    request: Request,
    target_nit: str | None = None,
    target_factura: str | None = None,
    detail: str | None = None,
) -> None:
    _log_access_event(
        action=action,
        request=request,
        user_id=session.user.id,
        username_snapshot=session.user.username,
        target_nit=target_nit,
        target_factura=target_factura,
        detail=detail,
    )
