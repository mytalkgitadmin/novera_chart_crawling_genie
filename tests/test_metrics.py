import pandas as pd

from chart_maker.metrics import add_metrics


def test_add_metrics_basic():
    df = pd.DataFrame(
        [
            {
                "platform": "GENIE",
                "song_id": "1",
                "timestamp": pd.to_datetime("2025-12-17 10:00"),
                "total_plays": 100,
                "total_listeners": 50,
            },
            {
                "platform": "GENIE",
                "song_id": "1",
                "timestamp": pd.to_datetime("2025-12-17 10:10"),
                "total_plays": 120,
                "total_listeners": 60,
            },
        ]
    )

    df_metrics, num_anomalies = add_metrics(df)
    assert "delta_plays" in df_metrics.columns
    assert "rate_plays_per_min" in df_metrics.columns
    assert num_anomalies == 0


