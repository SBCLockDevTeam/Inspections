from alarm_inspection.api.pdf_templates import (
    default_template_download_name,
    list_templates,
    normalize_template_field_values,
    template_meta,
)


def test_template_registry_contains_nfpa72():
    keys = {item["key"] for item in list_templates()}
    assert "nfpa72" in keys
    meta = template_meta("nfpa72")
    assert meta is not None
    assert meta["default_filename"] == "NFPA72_template.pdf"


def test_normalize_template_field_values_filters_unknown_fields():
    allowed = ["FieldA", "FieldB"]
    normalized = normalize_template_field_values(
        {
            "FieldA": " Value A ",
            "FieldB": 123,
            "Other": "ignored",
        },
        allowed,
    )
    assert normalized == {"FieldA": "Value A", "FieldB": "123"}


def test_default_template_download_name_is_sanitized():
    assert default_template_download_name("nfpa72", "4388") == "4388-nfpa72-updated.pdf"
    assert default_template_download_name("nfpa72", " 4/3:88 ") == "4388-nfpa72-updated.pdf"
