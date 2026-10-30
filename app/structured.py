def _entry(meta):
    if isinstance(meta, list):
        return meta[0] if meta else None
    return meta if isinstance(meta, dict) else None


def _scores(entry):
    if not entry:
        return None, None
    if entry.get("recognitionScore") is not None:
        return entry["recognitionScore"], None
    confidence = entry.get("confidence")
    if isinstance(confidence, dict):
        return confidence.get("ocr"), confidence.get("groundedness")
    if isinstance(confidence, (int, float)):
        return confidence, None
    return None, None


def _location(entry):
    if not entry:
        return None, None
    bbox = entry.get("bbox")
    page = entry.get("page")
    if not bbox:
        citation = entry.get("citation") or {}
        regions = citation.get("regions") if isinstance(citation, dict) else None
        if regions:
            bbox = regions[0].get("bbox")
            page = regions[0].get("page")
    if not bbox:
        return None, page
    return {"x": bbox["x"], "y": bbox["y"], "width": bbox["width"], "height": bbox["height"]}, page


def rows(values: dict, metadata: dict) -> list[dict]:
    out = []
    for field, value in values.items():
        if value is None or isinstance(value, dict):
            continue
        if isinstance(value, list) and (not value or isinstance(value[0], dict)):
            continue
        entry = _entry(metadata.get(field))
        bounds, page = _location(entry)
        parse, grounding = _scores(entry)
        citation = (entry or {}).get("citation") or {}
        out.append(
            {
                "field": field,
                "value": ", ".join(str(v) for v in value) if isinstance(value, list) else value,
                "confidence": parse,
                "grounding": grounding,
                "match": (entry or {}).get("match") or (citation.get("status") if isinstance(citation, dict) else None),
                "page": page,
                "bounds": bounds,
            }
        )
    return out


def highlights(field_rows: list[dict]) -> list[dict]:
    return [
        {"field": r["field"], "page": r["page"], "bounds": r["bounds"]}
        for r in field_rows
        if r["bounds"] and r["page"]
    ]
