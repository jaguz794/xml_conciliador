from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.api.dependencies import get_admin_session, get_current_session
from backend.app.models.schemas import (
    AuthUser,
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    UpdateUserRequest,
    UserActivityItem,
    UserDailyConsultationItem,
    UserSummary,
)
from backend.app.services.auth_service import (
    ACTION_CREATE_USER,
    ACTION_UPDATE_USER,
    SessionContext,
    authenticate_user,
    create_user,
    list_user_activity,
    list_user_daily_consultations,
    list_users_with_stats,
    log_user_action,
    revoke_session,
    update_user,
)

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    return authenticate_user(payload.username, payload.password, request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    session: SessionContext = Depends(get_current_session),
) -> None:
    revoke_session(session, request)


@router.get("/me", response_model=AuthUser)
def me(session: SessionContext = Depends(get_current_session)) -> AuthUser:
    return session.user


@router.get("/users", response_model=list[UserSummary])
def get_users(_: SessionContext = Depends(get_admin_session)) -> list[UserSummary]:
    return list_users_with_stats()


@router.get("/users/{user_id}/activity", response_model=list[UserActivityItem])
def get_user_activity(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    _: SessionContext = Depends(get_admin_session),
) -> list[UserActivityItem]:
    return list_user_activity(user_id, limit=limit)


@router.get("/users/{user_id}/daily-consultations", response_model=list[UserDailyConsultationItem])
def get_user_daily_consultations(
    user_id: int,
    limit: int = Query(default=30, ge=1, le=365),
    _: SessionContext = Depends(get_admin_session),
) -> list[UserDailyConsultationItem]:
    return list_user_daily_consultations(user_id, limit=limit)


@router.post("/users", response_model=AuthUser, status_code=status.HTTP_201_CREATED)
def create_app_user(
    payload: CreateUserRequest,
    request: Request,
    session: SessionContext = Depends(get_admin_session),
) -> AuthUser:
    try:
        created = create_user(
            username=payload.username,
            full_name=payload.full_name,
            password=payload.password,
            is_admin=payload.is_admin,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_user_action(
        session,
        action=ACTION_CREATE_USER,
        request=request,
        detail=f"Usuario creado: {created.username}",
    )
    return created


@router.patch("/users/{user_id}", response_model=AuthUser)
def update_app_user(
    user_id: int,
    payload: UpdateUserRequest,
    request: Request,
    session: SessionContext = Depends(get_admin_session),
) -> AuthUser:
    try:
        updated = update_user(
            user_id,
            full_name=payload.full_name,
            password=payload.password,
            is_admin=payload.is_admin,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_user_action(
        session,
        action=ACTION_UPDATE_USER,
        request=request,
        detail=f"Usuario actualizado: {updated.username}",
    )
    return updated
