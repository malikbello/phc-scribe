# ADR-0011: Standards: WHO ANC DAK, LOINC, ICD-11, FHIR R4 with Provenance

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Government procurement and national interoperability (NDHI, DHIS2) require standards. Clinical AI needs accountability.

## Decision
Align data elements to the WHO SMART Guidelines ANC Digital Adaptation Kit. Code vitals in LOINC and conditions in ICD-11 (SNOMED CT is avoided because it needs a country license). Export FHIR R4 Bundles that include a Provenance resource recording which model drafted the record and which worker confirmed it. Export DHIS2 aggregate dataValueSets.

## Consequences
Mapping work up front, in exchange for plug-in interoperability.
