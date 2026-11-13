# app/core/exceptions.py
class OpenWealthError(Exception):
    """Base para todos os erros do domínio."""

class PluggyError(OpenWealthError):
    """Falha na integração com a Pluggy (API fora, token inválido, etc.)."""

class SyncError(OpenWealthError):
    """Falha ao consolidar/persistir um snapshot."""
