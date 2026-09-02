# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : data.utils_fs
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Resolves the user's Documents folder via the Windows registry (respecting OneDrive redirection) and ensures a subfolder exists.
#                 Resolve a pasta Documentos do usuário via registro do Windows (respeitando o redirecionamento do OneDrive) e garante que uma subpasta exista.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from pathlib import Path


def pasta_documentos(subpasta: str) -> Path:
    """Resolve the user's 'Documents' folder and return a subfolder inside it, creating it if needed.

    Args:
        subpasta: Path relative to Documents, e.g., "AC's Generator/Relatórios".

    Returns:
        Path: Resolved folder, already created on disk.

    Notes:
        The 'Documents' folder is read from the Windows registry (the "Personal" key
        under Shell Folders) instead of assuming Path.home() / "Documents", since that
        is what honors redirections such as OneDrive's. If reading the registry fails
        for any reason, it falls back to Path.home() / "Documents".
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        docs = winreg.QueryValueEx(key, "Personal")[0]
        winreg.CloseKey(key)
    except Exception:
        docs = Path.home() / "Documents"

    pasta = Path(docs) / subpasta
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
