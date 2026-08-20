from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.services.auth_service import SessionContext, get_session_context

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> SessionContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesion para usar la aplicacion.",
        )

    session = get_session_context(credentials.credentials)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion no es valida o ya vencio. Ingresa nuevamente.",
        )

    return session


def get_application_session(session: SessionContext = Depends(get_current_session)) -> SessionContext:
    if session.user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contrasena antes de usar la aplicacion.",
        )
    return session


def get_admin_session(session: SessionContext = Depends(get_application_session)) -> SessionContext:
    if not session.user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta accion requiere un usuario administrador.",
        )
    return session
