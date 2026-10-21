
from pathlib import Path, PurePosixPath
import re


def validate_name(name: str) -> str:
    """Valida il nome di una cartella o di un file."""
    name = name.strip()

    if not name or name in {".", ".."}:
        raise ValueError(f"Nome non valido: {name!r}")

    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError(f"Caratteri non consentiti nel nome: {name}")

    if name.endswith(".") or name.endswith(" "):
        raise ValueError("Il nome non può terminare con punto o spazio.")

    return name


def create_structure(
    base_dir: str | Path,
    file_paths: list[str],
) -> list[Path]:
    """
    Crea cartelle e file .txt da un elenco di percorsi relativi.

    Esempi di percorsi:
    Beni/Proprietà.txt
    Beni/Possesso.txt
    Obbligazioni/Adempimento.txt

    Non sovrascrive file esistenti.
    """
    base = Path(base_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)

    if not file_paths:
        raise ValueError("L'elenco dei file è vuoto.")

    validated_paths = []
    seen = set()

    for raw_path in file_paths:
        raw_path = raw_path.strip().replace("\\", "/")

        if not raw_path:
            continue

        relative = PurePosixPath(raw_path)

        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Percorso non consentito: {raw_path}")

        parts = list(relative.parts)

        if not parts:
            raise ValueError("Percorso vuoto.")

        parts = [validate_name(part) for part in parts]

        filename = parts[-1]

        if Path(filename).suffix.lower() == ".txt":
            parts[-1] = filename[:-4]
            if not parts[-1]:
                raise ValueError("Il nome del file non può essere vuoto.")
        elif Path(filename).suffix:
            raise ValueError(
                f"È consentita soltanto l'estensione .txt: {filename}"
            )

        parts[-1] = validate_name(parts[-1])
        relative_path = PurePosixPath(*parts).with_suffix(".txt")
        normalized = relative_path.as_posix()

        if normalized.casefold() in seen:
            raise ValueError(f"Percorso duplicato: {normalized}")

        seen.add(normalized.casefold())
        validated_paths.append(normalized)

    # Verifica tutti i conflitti prima di creare nuovi file.
    targets = [base.joinpath(*PurePosixPath(p).parts) for p in validated_paths]

    for target in targets:
        if not target.resolve().is_relative_to(base):
            raise ValueError("Il percorso esce dalla cartella di lavoro.")

        if target.exists():
            raise FileExistsError(f"Il file esiste già: {target}")

    created_files = []

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=False)
        created_files.append(target)

    return created_files



