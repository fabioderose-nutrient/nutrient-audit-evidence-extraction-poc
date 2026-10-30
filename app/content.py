def page_sizes(content: dict) -> list[dict]:
    return [
        {
            "page": page.get("pageNumber"),
            "width": page.get("width"),
            "height": page.get("height"),
        }
        for page in content.get("metadata", [])
    ]


def plain_text(content: dict) -> str:
    lines = []
    for element in content.get("elements", []):
        text = (element.get("text") or "").strip()
        if text:
            lines.append(text)
        for cell in element.get("cells", []) or []:
            cell_text = (cell.get("text") or "").strip()
            if cell_text:
                lines.append(cell_text)
    return "\n".join(lines)


def word_boxes(content: dict) -> list[dict]:
    boxes = []
    for element in content.get("elements", []):
        page = element.get("pageNumber", 1)
        for word in element.get("words", []):
            bounds = word.get("bounds")
            if not bounds:
                continue
            boxes.append(
                {
                    "text": word.get("text", ""),
                    "page": page,
                    "confidence": word.get("confidence"),
                    "bounds": bounds,
                }
            )
    return boxes


def locate(boxes: list[dict], value) -> dict | None:
    if value is None:
        return None
    needle = str(value).strip()
    if not needle:
        return None
    tokens = [t for t in needle.split() if t]
    if not tokens:
        return None
    for i in range(len(boxes)):
        if boxes[i]["text"].strip(" ,:;") != tokens[0]:
            continue
        window = boxes[i : i + len(tokens)]
        if len(window) < len(tokens):
            continue
        if all(window[k]["text"].strip(" ,:;") == tokens[k] for k in range(len(tokens))):
            return _union(window)
    for box in boxes:
        if needle and needle in box["text"]:
            return _union([box])
    return None


def _union(window: list[dict]) -> dict:
    x0 = min(b["bounds"]["x"] for b in window)
    y0 = min(b["bounds"]["y"] for b in window)
    x1 = max(b["bounds"]["x"] + b["bounds"]["width"] for b in window)
    y1 = max(b["bounds"]["y"] + b["bounds"]["height"] for b in window)
    confidences = [b["confidence"] for b in window if b["confidence"] is not None]
    return {
        "page": window[0]["page"],
        "bounds": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
        "confidence": min(confidences) if confidences else None,
    }
