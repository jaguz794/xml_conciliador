from backend.app.services.archive_cleanup_service import cleanup_expired_runtime_files


def main() -> None:
    result = cleanup_expired_runtime_files()
    print(
        "Limpieza runtime completada | "
        f"zip_escaneados={result.processed_zips.scanned} "
        f"zip_eliminados={result.processed_zips.deleted} "
        f"zip_conservados={result.processed_zips.kept} "
        f"cache_escaneados={result.reconciliation_cache.scanned} "
        f"cache_eliminados={result.reconciliation_cache.deleted} "
        f"cache_conservados={result.reconciliation_cache.kept}"
    )
    for filename in result.processed_zips.deleted_files:
        print(f"ZIP ELIMINADO {filename}")
    for filename in result.reconciliation_cache.deleted_files:
        print(f"CACHE ELIMINADO {filename}")


if __name__ == "__main__":
    main()
