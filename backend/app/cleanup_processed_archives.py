from backend.app.services.archive_cleanup_service import cleanup_expired_processed_zips


def main() -> None:
    result = cleanup_expired_processed_zips()
    print(
        "Limpieza ZIP completada | "
        f"escaneados={result.scanned} "
        f"eliminados={result.deleted} "
        f"conservados={result.kept}"
    )
    for filename in result.deleted_files:
        print(f"ELIMINADO {filename}")


if __name__ == "__main__":
    main()
