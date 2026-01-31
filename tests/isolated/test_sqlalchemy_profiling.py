import pytest
from sqlalchemy import create_engine, text

from psynet.sqlalchemy_profiling import assert_query_count, sqlalchemy_profile


def test_sqlalchemy_profile_counts_queries():
    engine = create_engine("sqlite:///:memory:")
    with sqlalchemy_profile(engine) as profiler:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT 2"))

    assert profiler.total_count == 3
    stats = {stat.statement: stat for stat in profiler.get_stats()}
    assert stats["SELECT 1"].count == 2
    assert stats["SELECT 2"].count == 1
    assert profiler.total_time_ms >= 0.0


def test_assert_query_count_raises_when_exceeded():
    engine = create_engine("sqlite:///:memory:")
    with pytest.raises(AssertionError, match="Expected between 0 and 1 queries"):
        with assert_query_count(max_queries=1, engine=engine):
            with engine.begin() as conn:
                conn.execute(text("SELECT 1"))
                conn.execute(text("SELECT 1"))
