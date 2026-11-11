"""Deterministic intake checks for a report change or migration request."""

ROLES = ("BI_BA", "ARCHITECT", "DEVELOPER", "TESTER")


def assess(request, catalog, observed_columns=None):
    if not isinstance(request, dict):
        raise ValueError("A requirement must be a JSON object")
    findings = []

    def finding(code, role, message, severity="clarify"):
        findings.append({"code": code, "role": role, "message": message, "severity": severity})

    kind = request.get("type")
    if kind not in ("report_change", "migration"):
        raise ValueError("type must be report_change or migration")
    if type(request.get("version")) is not int or request["version"] < 1:
        raise ValueError("version must be a positive integer")
    for field in ("id", "title"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise ValueError(f"{field} must be a nonempty string")
    if not request.get("metric_definition"):
        finding("METRIC_UNDEFINED", "BI_BA", "Confirm numerator, denominator, geography and filters.")
    if not request.get("acceptance_criteria"):
        finding("ACCEPTANCE_MISSING", "TESTER", "Define expected outcomes and numeric tolerances.")
    if request.get("output_grain") not in catalog["supported_output_grains"]:
        finding("GRAIN_UNSUPPORTED", "ARCHITECT",
                "Use a supported grain or submit a revised model design.", "blocker")

    fields = request.get("required_source_fields", [])
    if not isinstance(fields, list) or any(not isinstance(field, str) or not field for field in fields):
        raise ValueError("required_source_fields must be a list of field names")
    for field in fields:
        if observed_columns is None:
            available = field in catalog["available_source_fields"]
        else:
            available = all(field in cols for cols in observed_columns)
        if not available:
            finding(f"FIELD_MISSING_{field}", "DEVELOPER",
                    f"{field} is unavailable in at least one requested source snapshot.")

    comparison = None
    if kind == "migration":
        legacy = request.get("legacy", {})
        if not isinstance(legacy, dict) or not isinstance(legacy.get("model", {}), dict):
            raise ValueError("legacy and legacy.model must be objects")
        for key, role, message in (
            ("architecture", "ARCHITECT", "Attach or describe the legacy architecture."),
            ("model", "ARCHITECT", "Provide legacy grain, keys and source fields."),
            ("baseline", "TESTER", "Supply a baseline from the same source snapshot and filters."),
        ):
            if not legacy.get(key):
                finding(f"LEGACY_{key.upper()}_MISSING", role, message)
        if legacy.get("model") and legacy["model"].get("grain") != catalog["fact_grain"]:
            finding("LEGACY_GRAIN_DIFF", "ARCHITECT",
                    "Document the grain conversion and how totals will be preserved.")
        if legacy.get("model") and legacy["model"].get("key") != catalog["fact_key"]:
            finding("KEY_MAPPING_REQUIRED", "ARCHITECT",
                    "Approve how the legacy key maps to the target fact key.")
        model = legacy.get("model", {})
        model_fields = model.get("fields", [])
        if not isinstance(model_fields, list) or any(not isinstance(f, str) for f in model_fields):
            raise ValueError("legacy.model.fields must be a list of field names")
        unmapped = sorted(set(model_fields) - set(catalog["field_mapping"]))
        if unmapped:
            finding("UNMAPPED_LEGACY_FIELDS", "DEVELOPER",
                    f"Confirm whether to migrate or retire: {', '.join(unmapped)}.")
        comparison = {
            "legacy_architecture": legacy.get("architecture"),
            "target_architecture": catalog["target_architecture"],
            "legacy_grain": model.get("grain"), "target_grain": catalog["fact_grain"],
            "legacy_key": model.get("key"), "target_key": catalog["fact_key"],
            "field_mapping": {f: catalog["field_mapping"].get(f) for f in model_fields},
            "legacy_baseline": legacy.get("baseline"),
        }

    verdict = ("UNSUITABLE_AS_PROPOSED" if any(f["severity"] == "blocker" for f in findings)
               else "NEEDS_CLARIFICATION" if findings else "SUITABLE")
    return {"id": request["id"], "version": request["version"], "title": request["title"],
            "type": kind, "verdict": verdict, "findings": findings,
            "migration_comparison": comparison}
