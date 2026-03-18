from deejay_sets_api.services.normalization import normalize_for_matching


def test_normalize_for_matching_basic():
    title, artist = normalize_for_matching("  Sundays  ", "Emotional Oranges ")
    assert title == "sundays"
    assert artist == "emotional oranges"


def test_normalize_for_matching_feat_and_suffixes():
    title, artist = normalize_for_matching("My Boo (Radio Edit)", "Artist feat. Someone")
    assert title == "my boo"
    assert artist == "artist"


def test_normalize_for_matching_clean_case_variants():
    title, artist = normalize_for_matching(
        "BURN THE HOUSE DOWN (Clean Version)", "  Burn The House Down  "
    )
    assert title == "burn the house down"
    assert artist == "burn the house down"
