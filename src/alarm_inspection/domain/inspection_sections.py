"""Shared identities for editable inspection fields and PDF source grouping."""
from typing import Literal

InspectionSection = Literal['compliance', 'nfpa72', 'store_data']
SECTION_LABELS = {'store_data': 'Store Data', 'compliance': 'Compliance', 'nfpa72': 'NFPA 72'}
