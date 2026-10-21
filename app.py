from pathlib import Path, PurePosixPath
from uuid import uuid4
import os
import re


import streamlit as st
from groq import Groq


from iris.archive import create_archive
from iris.content import fill_files
from iris.index_parser import parse_index
from iris.structure import create_structure
from iris.validation import verify_text_integrity
from iris.explorer import render_database_explorer




# ============================================================
# CONFIGURAZIONE
# ============================================================


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
DATABASE_ROOT = WORKSPACE / "database" / "Manuale Galgano"


st.set_page_config(
    page_title="IRIS — Assistente personale",
    page_icon="📚",
    layout="wide",
)


st.title("IRIS — Assistente personale")
st.caption(
    "Assistente personale con chat AI, esplorazione "
    "della banca dati e gestione controllata dei documenti."
)




# ============================================================
# FUNZIONI PER I PERCORSI
# ============================================================


def validate_paths(paths: list[str]) -> list[str]:
    """Convalida i percorsi relativi dei documenti."""


    if not paths:
        raise ValueError("Non è stato indicato alcun file.")


    result = []
    seen = set()


    for raw_path in paths:
        normalized = str(raw_path).strip().replace("\\", "/")
        relative = PurePosixPath(normalized)


        if (
            not normalized
            or relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.suffix.lower() != ".txt"
        ):
            raise ValueError(
                f"Percorso non consentito: {normalized}"
            )


        if any(part in {"", "."} for part in relative.parts):
            raise ValueError(
                f"Percorso non valido: {normalized}"
            )


        normalized = relative.as_posix()
        key = normalized.casefold()


        if key in seen:
            raise ValueError(
                f"Percorso duplicato: {normalized}"
            )


        seen.add(key)
        result.append(normalized)


    return result




def parse_paths(raw_paths: str) -> list[str]:
    """Converte un elenco di percorsi in file .txt."""


    if not raw_paths.strip():
        raise ValueError("Inserisci almeno un percorso.")


    paths = []
    seen = set()


    for line_number, line in enumerate(
        raw_paths.splitlines(), start=1
    ):
        line = line.strip().replace("\\", "/")


        if not line:
            continue


        relative = PurePosixPath(line)


        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"Riga {line_number}: percorso non consentito: {line}"
            )


        if not relative.parts:
            raise ValueError(
                f"Riga {line_number}: percorso non valido."
            )


        if relative.suffix.lower() not in {"", ".txt"}:
            raise ValueError(
                f"Riga {line_number}: è consentita soltanto "
                "l'estensione .txt."
            )


        if relative.suffix.lower() == ".txt":
            normalized = relative.as_posix()
        else:
            normalized = relative.with_suffix(".txt").as_posix()


        key = normalized.casefold()


        if key in seen:
            raise ValueError(
                f"Percorso duplicato: {normalized}"
            )


        seen.add(key)
        paths.append(normalized)


    return validate_paths(paths)




# ============================================================
# SUDDIVISIONE DEI TESTI
# ============================================================


def split_by_headings(
    text: str,
    paths: list[str],
) -> dict[str, str]:
    """Divide un testo usando titoli su righe autonome."""


    if not text.strip():
        raise ValueError("Inserisci il testo originale.")


    title_to_path = {}


    for path in paths:
        title = PurePosixPath(path).stem


        if title in title_to_path:
            raise ValueError(
                f"Il titolo '{title}' identifica più file. "
                "Usa la modalità con marcatori."
            )


        title_to_path[title] = path


    found_sections = {}
    current_path = None
    current_lines = []
    text_before_first_heading = []


    def save_current_section():
        if current_path is not None:
            found_sections[current_path] = "\n".join(
                current_lines
            )


    for line in text.splitlines():
        if line.strip() in title_to_path:
            save_current_section()
            current_path = title_to_path[line.strip()]
            current_lines = [line]


        elif current_path is None:
            text_before_first_heading.append(line)


        else:
            current_lines.append(line)


    save_current_section()


    if any(line.strip() for line in text_before_first_heading):
        raise ValueError(
            "È presente del testo prima del primo titolo "
            "riconosciuto. Usa la modalità con marcatori "
            "oppure sposta il testo."
        )


    missing = [
        path for path in paths
        if path not in found_sections
    ]


    if missing:
        raise ValueError(
            "Non sono stati trovati questi titoli nel testo: "
            + ", ".join(missing)
        )


    return found_sections




def parse_marked_sections(
    text: str,
    paths: list[str],
) -> dict[str, str]:
    """Divide il testo usando [[percorso/file.txt]]."""


    if not text.strip():
        raise ValueError("Inserisci le sezioni originali.")


    allowed_paths = set(paths)
    sections = {}
    current_path = None
    current_lines = []
    marker_pattern = re.compile(r"^\[\[(.+?)\]\]$")


    def save_current_section():
        if current_path is not None:
            if current_path in sections:
                raise ValueError(
                    f"Il file '{current_path}' è indicato più volte."
                )


            sections[current_path] = "\n".join(current_lines)


    for line_number, line in enumerate(
        text.splitlines(), start=1
    ):
        stripped = line.strip()
        match = marker_pattern.fullmatch(stripped)


        if match:
            save_current_section()


            marker_path = (
                match.group(1).strip().replace("\\", "/")
            )


            if marker_path not in allowed_paths:
                raise ValueError(
                    f"Riga {line_number}: il marcatore "
                    f"'{marker_path}' non corrisponde "
                    "a un file previsto."
                )


            if (
                marker_path in sections
                or marker_path == current_path
            ):
                raise ValueError(
                    f"Il file '{marker_path}' è indicato più volte."
                )


            current_path = marker_path
            current_lines = []


        else:
            if current_path is None:
                if stripped:
                    raise ValueError(
                        f"Riga {line_number}: il testo deve "
                        "iniziare con un marcatore "
                        "[[percorso/file.txt]]."
                    )
                continue


            current_lines.append(line)


    save_current_section()


    missing = [
        path for path in paths
        if path not in sections
    ]


    if missing:
        raise ValueError(
            "Mancano le sezioni per: " + ", ".join(missing)
        )


    return sections




# ============================================================
# PREPARAZIONE E SCRITTURA SICURA
# ============================================================


def prepare_documents(
    paths: list[str],
    contents: dict[str, str],
) -> tuple[Path, bytes]:
    """
    Crea una copia di lavoro separata e uno ZIP.
    Non modifica la banca dati principale.
    """


    paths = validate_paths(paths)


    if set(paths) != set(contents):
        raise ValueError(
            "I percorsi e i contenuti dei documenti non coincidono."
        )


    job_dir = WORKSPACE / f"job_{uuid4().hex}"
    documents_dir = job_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=False)


    created_files = create_structure(documents_dir, paths)
    fill_files(documents_dir, contents)


    for relative_path, original_text in contents.items():
        saved_path = documents_dir / relative_path


        if not verify_text_integrity(
            original_text, saved_path
        ):
            raise ValueError(
                f"Verifica di integrità fallita: {relative_path}"
            )


    zip_path = job_dir / "iris_documents.zip"
    create_archive(documents_dir, zip_path)


    return job_dir, zip_path.read_bytes()




def write_to_database(
    contents: dict[str, str],
) -> list[str]:
    """
    Scrive i documenti nella banca dati locale.


    Rifiuta i percorsi esterni alla radice e non sovrascrive
    i file esistenti. Se una scrittura fallisce, elimina
    i file creati durante questa operazione.
    """


    paths = validate_paths(list(contents))


    if not DATABASE_ROOT.is_dir():
        raise FileNotFoundError(
            "La banca dati non è stata trovata nel percorso atteso: "
            f"{DATABASE_ROOT}"
        )


    root = DATABASE_ROOT.resolve()
    targets = {}


    for relative_path in paths:
        target = root.joinpath(*PurePosixPath(relative_path).parts)
        resolved_target = target.resolve()


        if not resolved_target.is_relative_to(root):
            raise ValueError(
                f"Destinazione esterna alla banca dati: {relative_path}"
            )


        if target.exists():
            raise FileExistsError(
                f"Il file esiste già: {relative_path}. "
                "Non verrà sovrascritto."
            )


        targets[relative_path] = target


    # Controlla anche i conflitti tra file e cartelle.
    for relative_path, target in targets.items():
        parent = target.parent


        while parent != root and parent.is_relative_to(root):
            if parent.exists() and not parent.is_dir():
                raise ValueError(
                    f"Un file esistente impedisce di creare "
                    f"la cartella per {relative_path}."
                )
            parent = parent.parent


    created = []


    try:
        for relative_path, target in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)


            # Modalità esclusiva: non apre un file già esistente.
            with target.open("x", encoding="utf-8", newline="") as file:
                file.write(contents[relative_path])


            created.append(relative_path)


            if not verify_text_integrity(
                contents[relative_path], target
            ):
                raise ValueError(
                    f"Verifica di integrità fallita: {relative_path}"
                )


    except Exception:
        for relative_path in reversed(created):
            try:
                targets[relative_path].unlink(missing_ok=True)
            except OSError:
                pass
        raise


    return created




# ============================================================
# STATO DELLA SESSIONE
# ============================================================


if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


if "iris_pending_contents" not in st.session_state:
    st.session_state.iris_pending_contents = None


if "iris_pending_zip" not in st.session_state:
    st.session_state.iris_pending_zip = None


if "iris_pending_paths" not in st.session_state:
    st.session_state.iris_pending_paths = None




# ============================================================
# INTERFACCIA UNIFICATA
# ============================================================


tab_chat, tab_database, tab_documents = st.tabs(
    [
        "💬 Chat con IRIS",
        "📚 Banca dati",
        "📝 Crea e organizza documenti",
    ]
)




# ============================================================
# 1. CHAT
# ============================================================


with tab_chat:
    st.subheader("Chat con IRIS")


    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


    prompt = st.chat_input(
        "Scrivi qui il tuo messaggio...",
        key="iris_chat_input",
    )


    if prompt:
        st.session_state.chat_messages.append(
            {"role": "user", "content": prompt}
        )


        with st.chat_message("user"):
            st.markdown(prompt)


        api_key = os.environ.get("GROQ_API_KEY")


        if not api_key:
            st.error(
                "GROQ_API_KEY non è disponibile. "
                "Verifica il secret di GitHub Codespaces."
            )


        else:
            try:
                client = Groq(api_key=api_key)


                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Ti chiami IRIS. Comunichi in italiano, "
                            "con precisione e chiarezza. Aiuti l'utente "
                            "a ragionare, pianificare e organizzare "
                            "il lavoro. In questa versione non puoi "
                            "modificare direttamente i file tramite "
                            "la chat. Le operazioni sui documenti "
                            "devono essere eseguite attraverso "
                            "gli strumenti dell'interfaccia e "
                            "confermate dall'utente. Non affermare "
                            "di aver eseguito operazioni non svolte. "
                            "Non inventare informazioni sui file."
                        ),
                    },
                    *st.session_state.chat_messages,
                ]


                with st.spinner("IRIS sta pensando..."):
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        temperature=0.3,
                        max_completion_tokens=1500,
                    )


                answer = (
                    response.choices[0].message.content
                    or "Non ho ricevuto una risposta testuale."
                )


                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer}
                )


                with st.chat_message("assistant"):
                    st.markdown(answer)


            except Exception as error:
                st.error(
                    "Errore durante la connessione a Groq. "
                    "Verifica la chiave, il modello e la connessione."
                )
                st.caption(str(error))


    if st.button(
        "Cancella conversazione",
        key="clear_chat",
    ):
        st.session_state.chat_messages = []
        st.rerun()




# ============================================================
# 2. ESPLORATORE DELLA BANCA DATI
# ============================================================


with tab_database:
    st.subheader("Banca dati Galgano")


    st.caption(
        "Esplora le cartelle, visualizza i documenti ed esporta "
        "selezioni tramite gli strumenti disponibili."
    )


    render_database_explorer()




# ============================================================
# 3. CREAZIONE E ORGANIZZAZIONE DEI DOCUMENTI
# ============================================================


with tab_documents:
    st.subheader("Crea documenti nella struttura scelta da te")


    st.warning(
        "La generazione prepara una copia di lavoro e uno ZIP. "
        "La banca dati principale viene modificata soltanto "
        "dopo la tua conferma esplicita."
    )


    st.markdown("### 1. Definisci la struttura")


    index_mode = st.radio(
        "Come vuoi definire la struttura?",
        [
            "Indice numerato",
            "Percorsi completi dei file",
        ],
        key="iris_index_mode",
    )


    if index_mode == "Indice numerato":
        raw_paths = st.text_area(
            "Indice gerarchico",
            height=180,
            placeholder=(
                "1. Proprietà\n"
                "1.1 Proprietà fondiaria\n"
                "1.1.1 Diritto di usufrutto.txt\n"
                "1.1.2 Possesso.txt"
            ),
            key="numbered_index",
        )


        st.caption(
            "Le voci senza .txt sono cartelle; le voci con .txt "
            "sono file, secondo le regole del parser dell'indice."
        )


    else:
        raw_paths = st.text_area(
            "Percorsi relativi dei file",
            height=180,
            placeholder=(
                "Beni/Proprietà.txt\n"
                "Beni/Possesso.txt"
            ),
            key="manual_paths",
        )


        st.caption(
            "I percorsi sono relativi alla cartella "
            "'Manuale Galgano'. L'estensione .txt viene aggiunta "
            "se manca."
        )


    st.markdown("### 2. Inserisci i testi")


    mode = st.radio(
        "Modalità di inserimento",
        [
            "Un testo unico con titoli riconoscibili",
            "Testi già separati con marcatori",
        ],
        key="iris_text_mode",
    )


    if mode == "Un testo unico con titoli riconoscibili":
        raw_text = st.text_area(
            "Testo originale",
            height=350,
            placeholder=(
                "Proprietà\n"
                "Testo originale della sezione...\n\n"
                "Possesso\n"
                "Testo originale della sezione..."
            ),
            key="single_text",
        )


        st.caption(
            "Ogni titolo deve comparire su una riga autonoma "
            "ed essere identico al nome del file senza .txt."
        )


    else:
        raw_text = st.text_area(
            "Sezioni originali",
            height=350,
            placeholder=(
                "[[Beni/Proprietà.txt]]\n"
                "Testo originale della proprietà...\n\n"
                "[[Beni/Possesso.txt]]\n"
                "Testo originale del possesso..."
            ),
            key="marked_text",
        )


        st.caption(
            "Usa [[percorso/file.txt]] per assegnare ogni sezione "
            "al percorso che hai indicato. I marcatori non vengono "
            "salvati nel contenuto dei file."
        )


    st.markdown("### 3. Regole di integrità")


    st.write(
        "- La struttura e i percorsi li scegli tu.\n"
        "- Nessuna parafrasi automatica del testo.\n"
        "- Codifica UTF-8.\n"
        "- Verifica dell'integrità dopo la scrittura.\n"
        "- Nessuna sovrascrittura dei file esistenti.\n"
        "- Nessun caricamento automatico su Hugging Face."
    )


    if st.button(
        "Prepara anteprima e ZIP",
        type="primary",
        key="prepare_documents",
    ):
        try:
            if index_mode == "Indice numerato":
                paths = parse_index(raw_paths)
                paths = validate_paths(paths)
            else:
                paths = parse_paths(raw_paths)


            if mode == "Un testo unico con titoli riconoscibili":
                contents = split_by_headings(raw_text, paths)
            else:
                contents = parse_marked_sections(raw_text, paths)


            # Verifica che il testo sia stato assegnato esattamente
            # ai percorsi previsti.
            if set(paths) != set(contents):
                raise ValueError(
                    "I percorsi e i testi risultanti non coincidono."
                )


            _, zip_data = prepare_documents(paths, contents)


            st.session_state.iris_pending_contents = contents
            st.session_state.iris_pending_paths = paths
            st.session_state.iris_pending_zip = zip_data


            st.success(
                f"Anteprima pronta: {len(paths)} documenti "
                "preparati e verificati. Nessun file è stato "
                "ancora aggiunto alla banca dati principale."
            )


        except Exception as error:
            st.error(f"Preparazione non completata: {error}")


    # L'anteprima resta visibile dopo il rerun di Streamlit.
    pending = st.session_state.iris_pending_contents
    pending_paths = st.session_state.iris_pending_paths
    pending_zip = st.session_state.iris_pending_zip


    if pending and pending_paths:
        st.divider()
        st.markdown("### 4. Controlla l'anteprima")


        st.caption(
            "Controlla nomi, percorsi e contenuti prima di "
            "autorizzare la scrittura nella banca dati."
        )


        for relative_path in pending_paths:
            with st.expander(relative_path, expanded=False):
                st.text_area(
                    f"Contenuto: {relative_path}",
                    value=pending[relative_path],
                    height=220,
                    disabled=True,
                    key=f"preview_{relative_path}",
                )


        if pending_zip:
            st.download_button(
                label="Scarica lo ZIP di anteprima",
                data=pending_zip,
                file_name="iris_documents.zip",
                mime="application/zip",
                key="download_pending_zip",
            )


        st.markdown("### 5. Conferma la scrittura")


        st.warning(
            "La conferma aggiunge i documenti alla cartella "
            "'Manuale Galgano' nel Codespace. Controlla che i "
            "percorsi siano quelli desiderati."
        )


        confirm = st.checkbox(
            "Ho controllato i percorsi e i contenuti e autorizzo "
            "la creazione dei nuovi file nella banca dati locale.",
            key="confirm_database_write",
        )


        if st.button(
            "Conferma e crea i file nella banca dati",
            type="primary",
            disabled=not confirm,
            key="commit_documents",
        ):
            try:
                created = write_to_database(pending)


                st.success(
                    f"Operazione completata: {len(created)} "
                    "file creati e verificati nella banca dati locale."
                )


                for relative_path in created:
                    st.code(relative_path, language=None)


                st.info(
                    "Hugging Face non è stato modificato. "
                    "Quando vorrai aggiornare il dataset remoto, "
                    "potrai farlo manualmente."
                )


                st.session_state.iris_pending_contents = None
                st.session_state.iris_pending_paths = None
                st.session_state.iris_pending_zip = None
                st.session_state.confirm_database_write = False


            except Exception as error:
                st.error(
                    f"Scrittura non completata: {error}"
                )
                st.caption(
                    "Controlla i conflitti tra file e cartelle. "
                    "I file già esistenti non vengono sovrascritti."
                )


        if st.button(
            "Annulla l'anteprima",
            key="cancel_pending_documents",
        ):
            st.session_state.iris_pending_contents = None
            st.session_state.iris_pending_paths = None
            st.session_state.iris_pending_zip = None
            st.session_state.confirm_database_write = False
            st.rerun()
