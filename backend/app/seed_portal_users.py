from __future__ import annotations

from backend.app.services.auth_service import initialize_auth_system, seed_user_account

TEMP_PASSWORD = "123456"

DEFAULT_PORTAL_USERS = [
    {
        "username": "admin",
        "full_name": "Administrador",
        "is_admin": True,
    },
    {
        "username": "10814140",
        "full_name": "BRAND LOAIZA ANGELA YISELA",
        "is_admin": False,
    },
    {
        "username": "DBORRERO",
        "full_name": "BORRERO OBANDO DAGO ANDRES",
        "is_admin": False,
    },
    {
        "username": "KATERINE",
        "full_name": "CASAS BOHADA YULI CATERINE",
        "is_admin": False,
    },
    {
        "username": "LGARCIA",
        "full_name": "GARCIA CALDERON LUZ MARINA",
        "is_admin": False,
    },
    {
        "username": "DGARZON",
        "full_name": "GARZON HUACA DEISY",
        "is_admin": False,
    },
    {
        "username": "DNARANJO",
        "full_name": "NARANJO MUÑOZ DIANA CAROLINA",
        "is_admin": False,
    },
    {
        "username": "PERDOMO",
        "full_name": "PERDOMO AGUIRRE ZAIRA CAMILA",
        "is_admin": False,
    },
    {
        "username": "ERAMIREZ",
        "full_name": "RAMIREZ RODRIGUEZ EDNA ROCIO",
        "is_admin": False,
    },
    {
        "username": "NSERRANO",
        "full_name": "SERRANO JIMENEZ NORMA CONSTANZA",
        "is_admin": False,
    },
    {
        "username": "PAULA A",
        "full_name": "UNI GUTIERREZ PAULA ANDREA",
        "is_admin": False,
    },
]


def main() -> None:
    initialize_auth_system()
    print("Creando o actualizando usuarios base del portal...")

    for item in DEFAULT_PORTAL_USERS:
        user, created = seed_user_account(
            username=item["username"],
            full_name=item["full_name"],
            password=TEMP_PASSWORD,
            is_admin=bool(item["is_admin"]),
            is_active=True,
            must_change_password=True,
        )
        action = "creado" if created else "actualizado"
        role = "admin" if user.is_admin else "consulta"
        print(f"- {action}: {user.username} | {user.full_name} | perfil={role} | cambio_clave=si")

    print("Proceso finalizado. Todos los usuarios quedaron con contrasena temporal 123456.")


if __name__ == "__main__":
    main()
