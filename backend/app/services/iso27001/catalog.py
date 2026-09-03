"""ISO/IEC 27001:2022 Annex A control catalog — a bounded, self-disclosing
subset, NOT sourced from a licensed copy of the standard.

**Read this before touching or trusting this file's data.** The user
explicitly decided (after being asked, since ISO 27001's Annex A text is
copyrighted and this project has no licensed copy) that this catalog
should be seeded with control IDs and short titles as they are widely
discussed in public secondary sources — never the standard's own
normative clause text. Every entry below carries its own `source_note`
saying exactly this, so the disclaimer travels with the data wherever
it's read (API responses, findings, docs) rather than living only in this
comment. `description` is this project's own one-line paraphrase of the
control's general subject, not a copy of anything.

**Scope**: 48 of the real standard's 93 controls, concentrated where
code-level evidence is plausible — all 34 Technological (A.8) controls
(6 marked `automatable=False` where the control is organizational in
practice despite the theme: user endpoint devices, capacity management,
redundancy, clock sync, software-installation governance, outsourced
development) plus 14 Organizational (A.5) controls that either match the
compliance-scanner spec's own listed assessment areas or have a plausible
existing Finding category to map from (asset inventory, classification,
supplier relationships, incident management, legal/regulatory, privacy).
**People (A.6, 8 controls) and Physical (A.7, 14 controls) are
deliberately not catalogued this phase** — zero existing Finding category
from Phases 2-4 relates to personnel/HR security, and physical-security
controls are structurally unassessable from a source-code repository scan
under any circumstance; cataloguing them just to mark every one
unassessable would be cosmetic completeness, not real value.
"""

from __future__ import annotations

from dataclasses import dataclass

_SOURCE_NOTE = (
    "Control ID and title reflect the publicly-known structure of ISO/IEC "
    "27001:2022 Annex A as discussed in public secondary sources. This is "
    "NOT sourced from the licensed standard, has not been verified against "
    "the official text, and must not be treated as a substitute for a "
    "licensed copy of ISO/IEC 27001:2022."
)


@dataclass(frozen=True)
class ISO27001Control:
    control_id: str
    title: str
    theme: str  # "Organizational" | "People" | "Physical" | "Technological"
    description: str  # this project's own paraphrase — never the standard's text
    assessment_type: str  # "technical" | "organizational"
    automatable: bool
    evidence_types: tuple[str, ...]
    source_note: str = _SOURCE_NOTE


def _technical(
    control_id: str, title: str, description: str, *evidence_types: str
) -> ISO27001Control:
    return ISO27001Control(
        control_id=control_id,
        title=title,
        theme="Technological",
        description=description,
        assessment_type="technical",
        automatable=True,
        evidence_types=evidence_types,
    )


def _organizational_tech_theme(control_id: str, title: str, description: str) -> ISO27001Control:
    """A.8 control that sits in the Technological theme but is
    organizational in practice (e.g. "capacity management" is a process,
    not a code pattern) — still `theme="Technological"`, but not claimed
    as automatable.
    """
    return ISO27001Control(
        control_id=control_id,
        title=title,
        theme="Technological",
        description=description,
        assessment_type="organizational",
        automatable=False,
        evidence_types=("documentation",),
    )


def _organizational(control_id: str, title: str, description: str) -> ISO27001Control:
    return ISO27001Control(
        control_id=control_id,
        title=title,
        theme="Organizational",
        description=description,
        assessment_type="organizational",
        automatable=False,
        evidence_types=("documentation",),
    )


CATALOG: tuple[ISO27001Control, ...] = (
    # --- A.5 Organizational (14 of 37 catalogued) --------------------------
    _organizational(
        "A.5.9", "Inventory of information and other associated assets",
        "Maintaining an inventory of information assets and their owners.",
    ),
    _organizational(
        "A.5.12", "Classification of information",
        "Classifying information according to protection needs.",
    ),
    _organizational(
        "A.5.13", "Labelling of information",
        "Labelling information consistently with its classification.",
    ),
    _organizational(
        "A.5.19", "Information security in supplier relationships",
        "Defining and agreeing information security requirements with suppliers.",
    ),
    _organizational(
        "A.5.20", "Addressing information security within supplier agreements",
        "Establishing information security terms in supplier agreements.",
    ),
    _organizational(
        "A.5.21", "Managing information security in the ICT supply chain",
        "Managing information security risks in the ICT supply chain.",
    ),
    _organizational(
        "A.5.22", "Monitoring, review and change management of supplier services",
        "Monitoring and reviewing supplier service delivery and changes.",
    ),
    _organizational(
        "A.5.23", "Information security for use of cloud services",
        "Managing information security risk in the use of cloud services.",
    ),
    _organizational(
        "A.5.24", "Information security incident management planning and preparation",
        "Planning and preparing for information security incident management.",
    ),
    _organizational(
        "A.5.25", "Assessment and decision on information security events",
        "Assessing security events to decide whether they are incidents.",
    ),
    _organizational(
        "A.5.26", "Response to information security incidents",
        "Responding to information security incidents per a defined process.",
    ),
    _organizational(
        "A.5.27", "Learning from information security incidents",
        "Using knowledge from incidents to reduce future likelihood/impact.",
    ),
    _organizational(
        "A.5.31", "Legal, statutory, regulatory and contractual requirements",
        "Identifying and meeting legal/regulatory/contractual security obligations.",
    ),
    _organizational(
        "A.5.34", "Privacy and protection of PII",
        "Protecting personally identifiable information per applicable requirements.",
    ),
    # --- A.8 Technological (all 34 catalogued; 6 not automatable) ---------
    _organizational_tech_theme(
        "A.8.1", "User endpoint devices",
        "Protecting information on user endpoint devices.",
    ),
    _technical(
        "A.8.2", "Privileged access rights",
        "Restricting and managing privileged access rights.",
        "source_code", "configuration",
    ),
    _technical(
        "A.8.3", "Information access restriction",
        "Restricting access to information per an access-control policy.",
        "source_code", "configuration",
    ),
    _technical(
        "A.8.4", "Access to source code",
        "Managing read/write access to source code, tools, and libraries.",
        "configuration", "infrastructure",
    ),
    _technical(
        "A.8.5", "Secure authentication",
        "Implementing secure authentication technologies and procedures.",
        "source_code",
    ),
    _organizational_tech_theme(
        "A.8.6", "Capacity management",
        "Monitoring and adjusting resource capacity to meet requirements.",
    ),
    _technical(
        "A.8.7", "Protection against malware",
        "Implementing malware protection combined with user awareness.",
        "configuration", "infrastructure",
    ),
    _technical(
        "A.8.8", "Management of technical vulnerabilities",
        "Obtaining and acting on information about technical vulnerabilities, "
        "including dependency versions.",
        "dependency_manifest", "configuration",
    ),
    _technical(
        "A.8.9", "Configuration management",
        "Establishing, documenting, and monitoring secure configurations.",
        "configuration", "infrastructure",
    ),
    _technical(
        "A.8.10", "Information deletion",
        "Deleting information when no longer required.",
        "source_code", "documentation",
    ),
    _technical(
        "A.8.11", "Data masking",
        "Using data masking/anonymization/pseudonymization where relevant.",
        "source_code",
    ),
    _technical(
        "A.8.12", "Data leakage prevention",
        "Applying measures to prevent unauthorized disclosure of sensitive data.",
        "source_code", "configuration",
    ),
    _technical(
        "A.8.13", "Information backup",
        "Maintaining and testing backup copies of information and software.",
        "infrastructure", "configuration",
    ),
    _organizational_tech_theme(
        "A.8.14", "Redundancy of information processing facilities",
        "Implementing redundancy to meet availability requirements.",
    ),
    _technical(
        "A.8.15", "Logging",
        "Producing, storing, protecting, and reviewing logs of events.",
        "source_code", "configuration",
    ),
    _technical(
        "A.8.16", "Monitoring activities",
        "Monitoring systems for anomalous behavior and taking action.",
        "source_code", "configuration", "infrastructure",
    ),
    _organizational_tech_theme(
        "A.8.17", "Clock synchronization",
        "Synchronizing clocks against an agreed time source.",
    ),
    _technical(
        "A.8.18", "Use of privileged utility programs",
        "Restricting and controlling utility programs that could override controls.",
        "configuration",
    ),
    _organizational_tech_theme(
        "A.8.19", "Installation of software on operational systems",
        "Governing procedures for installing software on operational systems.",
    ),
    _technical(
        "A.8.20", "Networks security",
        "Managing and controlling networks to protect systems and applications.",
        "infrastructure", "configuration",
    ),
    _technical(
        "A.8.21", "Security of network services",
        "Identifying and including security features of network services.",
        "infrastructure", "configuration",
    ),
    _technical(
        "A.8.22", "Segregation of networks",
        "Segregating groups of information services/users/systems on networks.",
        "infrastructure", "configuration",
    ),
    _technical(
        "A.8.23", "Web filtering",
        "Managing access to external websites to reduce exposure to malicious content.",
        "configuration",
    ),
    _technical(
        "A.8.24", "Use of cryptography",
        "Rules governing the effective use of cryptography, including key management.",
        "source_code",
    ),
    _technical(
        "A.8.25", "Secure development life cycle",
        "Applying rules for secure software/system development.",
        "source_code", "documentation",
    ),
    _technical(
        "A.8.26", "Application security requirements",
        "Identifying and specifying application security requirements.",
        "source_code", "documentation",
    ),
    _technical(
        "A.8.27", "Secure system architecture and engineering principles",
        "Establishing and applying secure engineering principles.",
        "source_code", "documentation",
    ),
    _technical(
        "A.8.28", "Secure coding",
        "Applying secure coding principles to software development.",
        "source_code",
    ),
    _technical(
        "A.8.29", "Security testing in development and acceptance",
        "Defining and implementing security testing processes.",
        "source_code", "infrastructure",
    ),
    _organizational_tech_theme(
        "A.8.30", "Outsourced development",
        "Directing, monitoring, and reviewing outsourced system development.",
    ),
    _technical(
        "A.8.31", "Separation of development, test and production environments",
        "Separating and securing development/test/production environments.",
        "infrastructure", "configuration",
    ),
    _technical(
        "A.8.32", "Change management",
        "Subjecting changes to information processing facilities to a controlled process.",
        "source_code", "documentation",
    ),
    _technical(
        "A.8.33", "Test information",
        "Selecting, protecting, and managing test information appropriately.",
        "source_code", "configuration",
    ),
    _technical(
        "A.8.34", "Protection of information systems during audit testing",
        "Planning and agreeing audit tests to minimize disruption to systems.",
        "documentation",
    ),
)

CATALOG_BY_ID: dict[str, ISO27001Control] = {control.control_id: control for control in CATALOG}
