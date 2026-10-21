
from pathlib import Path
import hashlib


def text_fingerprint(text: str) -> str:
    """Calcola un'impronta digitale del testo ricevuto."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_fingerprint(file_path: str | Path) -> str:
    """Calcola l'impronta digitale del contenuto effettivo del file."""
    path = Path(file_path)

    with path.open("rb") as file:
        content = file.read()

    return hashlib.sha256(content).hexdigest()


def verify_text_integrity(
    original_text: str,
    file_path: str | Path,
) -> bool:
    """
    Verifica che il file contenga esattamente il testo originale
    codificato in UTF-8, senza modifiche.
    """
    path = Path(file_path)

    with path.open("rb") as file:
        saved_content = file.read()

    original_content = original_text.encode("utf-8")

    return saved_content == original_content


def compare_texts(original_text: str, final_text: str) -> dict:
    """Confronta due testi senza normalizzarli o modificarli."""
    identical = original_text == final_text

    return {
        "identical": identical,
        "original_characters": len(original_text),
        "final_characters": len(final_text),
        "original_sha256": text_fingerprint(original_text),
        "final_sha256": text_fingerprint(final_text),
    }


