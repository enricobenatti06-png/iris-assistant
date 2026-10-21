import re

from pathlib import PurePosixPath
from iris.structure import validate_name


def parse_index(raw_index: str) -> list[str]:
    """
    Converte un indice numerato in percorsi relativi.

    Le voci senza estensione .txt sono cartelle.
    Le voci con estensione .txt sono file.
    Il livello numerico determina la gerarchia.
    """

    if not isinstance(raw_index, str) or not raw_index.strip():
        raise ValueError("L'indice è vuoto.")

    stack: list[tuple[int, str]] = []
    paths: list[str] = []
    seen: set[str] = set()

    for line_number, line in enumerate(raw_index.splitlines(), start=1):
        line = line.strip()

        if not line:
            continue

        match = re.match(r"^(\d+(?:\.\d+)*\.?)\s+(.+?)$", line)

        if not match:
            raise ValueError(
                f"Riga {line_number}: usa una numerazione "
                "come '1. Proprietà' oppure '1.1 Proprietà fondiaria'."
            )

        numbering = match.group(1).rstrip(".")
        name = match.group(2).strip()
        depth = numbering.count(".") + 1

        if not name:
            raise ValueError(f"Riga {line_number}: nome mancante.")

        is_file = name.lower().endswith(".txt")

        if is_file:
            name = name[:-4]

        name = validate_name(name)

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if depth > 1:
            if not stack or stack[-1][0] != depth - 1:
                raise ValueError(
                    f"Riga {line_number}: manca la cartella "
                    f"genitore del livello {depth}."
                )

        parts = [folder_name for _, folder_name in stack]
        parts.append(name)

        if is_file:
            relative_path = PurePosixPath(*parts).with_suffix(".txt")
            path_string = relative_path.as_posix()

            if path_string.casefold() in seen:
                raise ValueError(f"Percorso duplicato: {path_string}")

            seen.add(path_string.casefold())
            paths.append(path_string)
        else:
            stack.append((depth, name))

    if not paths:
        raise ValueError("L'indice non contiene alcun file .txt.")

    return paths

