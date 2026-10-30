"""Presentation settings for existing native inspection properties, not checklist copies."""
from datetime import date
from alarm_inspection.domain.inspection_names import normalize_city, normalize_state

STORE_TYPES = ['Walmart - Supercenter', 'Walmart - Neighborhood Market', "Sam's Club"]
NATIVE_FIELDS = [
    ('store_number', 'Store Number', 'textbox', 100),
    ('store_type', 'Store Type', 'dropdown', 80),
    ('address', 'Address', 'textbox', 500),
    ('city', 'City', 'textbox', 120),
    ('state', 'State', 'textbox', 2),
    ('inspector_name', 'Inspector', 'textbox', 120),
    ('start_date', 'Start Date', 'date', 10),
    ('completion_date', 'End Date', 'date', 10),
]


def validate_native_default(field, value):
    definition = next(item for item in NATIVE_FIELDS if item[0] == field)
    value = value.strip()
    if len(value) > definition[3]:
        raise ValueError(f'Default must be at most {definition[3]} characters.')
    if value and definition[2] == 'date':
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Choose a date in YYYY-MM-DD format.')
    if value and field == 'store_type' and value not in STORE_TYPES:
        raise ValueError('Choose a current Store Type.')
    if value and field == 'state':
        value = normalize_state(value)
        if not value:
            raise ValueError('Enter a valid two-letter state abbreviation.')
    if value and field == 'city':
        value = normalize_city(value)
        if not value:
            raise ValueError('Enter a valid city.')
    return value
