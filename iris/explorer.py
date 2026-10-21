from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED


import streamlit as st




ROOT = (
    Path(__file__).resolve().parent.parent
    / "workspace"
    / "database"
    / "Manuale Galgano"
)




def render_database_explorer():
    if not ROOT.is_dir():
        st.error(f"Database non trovato: {ROOT}")
        return


    entries = sorted(
        (p for p in ROOT.rglob("*") if p.is_file()),
        key=lambda p: str(p.relative_to(ROOT)).lower(),
    )
    directories = sorted(
        (p for p in ROOT.rglob("*") if p.is_dir()),
        key=lambda p: str(p.relative_to(ROOT)).lower(),
    )


    selected_rel = st.session_state.get("iris_selected_document", "")
    selected_path = ROOT / selected_rel if selected_rel else None


    st.divider()
    st.header("Banca dati Galgano")
    st.caption(
        f"{len(directories)} cartelle · {len(entries)} file"
    )


    tree_col, preview_col = st.columns([1, 1.5], gap="large")


    with tree_col:
        st.subheader("Esplora")


        st.caption("Apri le cartelle per visualizzarne il contenuto.")


        def render_folder(folder: Path):
            rel = folder.relative_to(ROOT).as_posix()
            contains_selected = (
                bool(selected_rel)
                and (
                    selected_rel == rel
                    or selected_rel.startswith(rel + "/")
                )
            )


            children = sorted(
                folder.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower()),
            )


            with st.expander(
                f"📁 {folder.name}",
                expanded=contains_selected,
            ):
                for child in children:
                    child_rel = child.relative_to(ROOT).as_posix()


                    if child.is_dir():
                        render_folder(child)
                    else:
                        if st.button(
                            f"📄 {child.name}",
                            key=f"iris_open_{child_rel}",
                            use_container_width=True,
                            type=(
                                "primary"
                                if child_rel == selected_rel
                                else "secondary"
                            ),
                        ):
                            st.session_state[
                                "iris_selected_document"
                            ] = child_rel
                            st.rerun()


        root_children = sorted(
            ROOT.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower()),
        )


        for child in root_children:
            child_rel = child.relative_to(ROOT).as_posix()


            if child.is_dir():
                render_folder(child)
            else:
                if st.button(
                    f"📄 {child.name}",
                    key=f"iris_open_{child_rel}",
                    use_container_width=True,
                ):
                    st.session_state[
                        "iris_selected_document"
                    ] = child_rel
                    st.rerun()


    with preview_col:
        st.subheader("Anteprima documento")


        if selected_path and selected_path.is_file():
            st.caption(f"Percorso: Manuale Galgano/{selected_rel}")
            st.markdown(f"**{selected_path.name}**")


            try:
                content = selected_path.read_text(encoding="utf-8")
                st.text_area(
                    "Contenuto originale",
                    value=content,
                    height=500,
                    disabled=True,
                    key=f"iris_preview_{selected_rel}",
                )
                st.download_button(
                    "Scarica documento",
                    data=selected_path.read_bytes(),
                    file_name=selected_path.name,
                    mime="text/plain",
                    key=f"iris_download_{selected_rel}",
                )
            except (OSError, UnicodeError) as exc:
                st.error(f"Impossibile leggere il documento: {exc}")
        else:
            st.info(
                "Seleziona un file nell'albero a sinistra "
                "per visualizzarne il contenuto."
            )


    with st.expander("Esporta documenti in ZIP"):
        st.caption(
            "Seleziona file e cartelle. "
            "I percorsi relativi originali saranno mantenuti."
        )


        selectable = directories + entries
        selectable.sort(
            key=lambda p: str(p.relative_to(ROOT)).lower()
        )


        labels = {
            p.relative_to(ROOT).as_posix(): p
            for p in selectable
        }


        selected_items = st.multiselect(
            "File e cartelle da includere",
            options=list(labels.keys()),
            key="iris_zip_selection",
        )


        if st.button(
            "Prepara ZIP",
            disabled=not selected_items,
            key="iris_prepare_zip",
        ):
            files_to_zip = set()


            for item in selected_items:
                path = labels[item]


                if path.is_file():
                    files_to_zip.add(path)
                else:
                    files_to_zip.update(
                        p for p in path.rglob("*") if p.is_file()
                    )


            if not files_to_zip:
                st.warning("La selezione non contiene file.")
                st.session_state.pop("iris_zip_data", None)
            else:
                buffer = BytesIO()


                with ZipFile(
                    buffer, "w", ZIP_DEFLATED
                ) as archive:
                    for path in sorted(
                        files_to_zip,
                        key=lambda p: str(p).lower(),
                    ):
                        archive.write(
                            path,
                            arcname=path.relative_to(ROOT).as_posix(),
                        )


                st.session_state["iris_zip_data"] = buffer.getvalue()
                st.session_state["iris_zip_name"] = (
                    "galgano_selezione.zip"
                )


        if st.session_state.get("iris_zip_data"):
            st.download_button(
                "Scarica ZIP",
                data=st.session_state["iris_zip_data"],
                file_name=st.session_state.get(
                    "iris_zip_name",
                    "galgano_selezione.zip",
                ),
                mime="application/zip",
                key="iris_download_zip",
            )
