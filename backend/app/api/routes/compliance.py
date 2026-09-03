from fastapi import APIRouter

from app.services.iso27001.catalog import CATALOG

router = APIRouter(prefix="/compliance", tags=["compliance"])

# Top-level disclaimer, in addition to each entry's own `source_note` —
# belt-and-suspenders labeling so the unofficial-data caveat survives even
# a client that only reads the envelope and drops individual fields.
_ISO27001_DISCLAIMER = (
    "Control IDs and titles reflect the publicly-known structure of ISO/IEC "
    "27001:2022 Annex A as discussed in public secondary sources. This is NOT "
    "sourced from the licensed standard and must not be treated as a "
    "substitute for a licensed copy of ISO/IEC 27001:2022. This subset covers "
    "48 of the standard's 93 controls; People and Physical theme controls are "
    "not catalogued."
)


@router.get("/frameworks/iso27001/controls")
def list_iso27001_controls():
    return {
        "disclaimer": _ISO27001_DISCLAIMER,
        "controls": [
            {
                "control_id": control.control_id,
                "title": control.title,
                "theme": control.theme,
                "description": control.description,
                "assessment_type": control.assessment_type,
                "automatable": control.automatable,
                "evidence_types": list(control.evidence_types),
                "source_note": control.source_note,
            }
            for control in CATALOG
        ],
    }
