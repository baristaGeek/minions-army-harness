"""Database URL helpers."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_database_url(url: str, *, is_async: bool) -> str:
    """Normalize a SQLAlchemy URL for runtime or migration use."""
    parts = urlsplit(url)
    base, separator, driver = parts.scheme.partition("+")
    if base == "postgres":
        base = "postgresql"

    if is_async:
        new_scheme = "postgresql+asyncpg" if base == "postgresql" else parts.scheme
    else:
        new_scheme = base if separator and driver else base

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if is_async and base == "postgresql":
        query_pairs = [
            ("ssl", value) if key == "sslmode" else (key, value) for key, value in query_pairs
        ]
    query = urlencode(query_pairs)
    if parts.netloc == "" and "://" in url:
        suffix = urlunsplit(("", parts.netloc, parts.path, query, parts.fragment))
        return f"{new_scheme}://{suffix}"
    return urlunsplit((new_scheme, parts.netloc, parts.path, query, parts.fragment))
