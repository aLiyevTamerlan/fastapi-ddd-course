def normalize_text(value: str) -> str:
    """Trim and collapse inner whitespace, so ``"  Python   kursu "`` and ``"Python kursu"`` are one value."""
    return " ".join(value.split())
