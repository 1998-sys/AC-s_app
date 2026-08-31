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
    """
    Resolve a pasta 'Documentos' do usuário via registro do Windows (respeita
    pastas Documentos redirecionadas, ex.: OneDrive) e retorna uma subpasta
    dentro dela, criando-a se necessário.

    Args:
        subpasta (str): Caminho relativo dentro de Documentos, ex.: "AC's Generator/Relatórios".

    Returns:
        Path: pasta resolvida e já criada.
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
