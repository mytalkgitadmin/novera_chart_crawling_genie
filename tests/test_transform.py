import pandas as pd

from chart_maker.transform import normalize


def test_normalize_basic():
    df = pd.DataFrame(
        [
            {
                "platform": "GENIE",
                "song_id": "1",
                "song_name": "A",
                "artist_name": "AA",
                "date": "2025-12-17",
                "hour": 10,
                "minute": 0,
                "total_plays": 100,
                "total_listeners": 50,
            },
            {
                "platform": "GENIE",
                "song_id": "1",
                "song_name": "A",
                "artist_name": "AA",
                "date": "2025-12-17",
                "hour": 10,
                "minute": 0,
                "total_plays": 100,
                "total_listeners": 50,
            },
        ]
    )

    df_norm, dup_count = normalize(df)
    assert len(df_norm) == 1
    assert dup_count == 1
    assert "timestamp" in df_norm.columns


