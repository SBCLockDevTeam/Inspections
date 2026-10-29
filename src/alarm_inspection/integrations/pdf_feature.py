"""Small dependency-free, fail-closed switch independent of legacy PDF tools."""
import os


def enabled() -> bool:
    return os.getenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', '').strip().lower() in {'1', 'true'}


def require_available(session):
    if not enabled() or not session.info.get('pdf_integrations_available', False):
        raise RuntimeError('PDF integrations are disabled or unavailable.')
