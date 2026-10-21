
from pathlib import Path


def fill_file(
    file_path: str | Path,
    text: str,
    overwrite: bool = False,
) -> Path:
    """Scrive il testo ricevuto senza parafrasi o riformattazione."""
    path = Path(file_path)

    if path.suffix.lower() != ".txt":
        raise ValueError("Sono consentiti soltanto file .txt.")

    if not isinstance(text, str):
        raise TypeError("Il contenuto deve essere una stringa.")

    if not path.parent.is_dir():
        raise FileNotFoundError(
            f"La cartella non esiste: {path.parent}"
        )

    if path.exists():
        if not path.is_file():
            raise ValueError("La destinazione non è un file.")

        # Consente di riempire i file vuoti creati da structure.py.
        # I file già contenenti testo restano protetti.
        if path.stat().st_size > 0 and not overwrite:
            raise FileExistsError(
                f"Il file contiene già dati: {path}"
            )

    path.write_bytes(text.encode("utf-8"))
    return path


def fill_files(
    base_dir: str | Path,
    contents: dict[str, str],
) -> list[Path]:
    """Riempie file .txt esistenti usando percorsi relativi."""
    base = Path(base_dir).resolve()
    written_files = []

    for relative_path, text in contents.items():
        path = (base / relative_path).resolve()

        if not path.is_relative_to(base):
            raise ValueError(
                "Il percorso esce dalla cartella di lavoro."
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"Il file non esiste: {relative_path}"
            )

        fill_file(path, text)
        written_files.append(path)

    return written_files




