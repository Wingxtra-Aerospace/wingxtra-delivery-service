from app.services.ui_service import etag_matches


def test_etag_matches_accepts_exact_and_weak_match() -> None:
    etag = '"abc123"'

    assert etag_matches(etag, etag)
    assert etag_matches(f"W/{etag}", etag)


def test_etag_matches_accepts_list_and_wildcard() -> None:
    etag = '"abc123"'

    assert etag_matches(f'"other", {etag}', etag)
    assert etag_matches("*", etag)


def test_etag_matches_handles_quoted_comma_tokens() -> None:
    etag = '"abc123"'

    assert etag_matches('"a,b", "c,d", "abc123"', etag)
    assert not etag_matches('"a,b", "c,d"', etag)


def test_etag_matches_rejects_non_matching_and_empty_headers() -> None:
    etag = '"abc123"'

    assert not etag_matches(None, etag)
    assert not etag_matches("", etag)
    assert not etag_matches('"other"', etag)
