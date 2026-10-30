"""Shared identities for editable inspection fields and PDF source grouping."""
from typing import Literal

InspectionSection = Literal['compliance', 'nfpa72']
SECTION_LABELS = {'compliance': 'Compliance', 'nfpa72': 'NFPA 72'}
