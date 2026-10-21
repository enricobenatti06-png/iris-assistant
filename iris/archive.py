
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def create_archive(
    source_dir: str | Path,
    output_zip: str | Path,
) -> Path:
    """
    Crea un archivio ZIP della cartella di lavoro.

    Mantiene i percorsi relativi, include le cartelle vuote
    e non inserisce nell'archivio file diversi dai .txt.
    """
    source = Path(source_dir).resolve()
    destination = Path(output_zip).resolve()

    if not source.is_dir():
        raise NotADirectoryError(
            f"La cartella sorgente non esiste: {source}"
        )

    if destination == source or source in destination.parents:
        raise ValueError(
            "L'archivio ZIP deve essere salvato fuori dalla cartella sorgente."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for item in sorted(source.rglob("*")):
            if item.is_symlink():
                continue

            relative_path = item.relative_to(source).as_posix()

            if item.is_dir():
                # ZIP altrimenti non conserva le cartelle vuote.
                archive.writestr(relative_path.rstrip("/") + "/", "")

            elif item.is_file() and item.suffix.lower() == ".txt":
                archive.write(item, arcname=relative_path)

    return destination