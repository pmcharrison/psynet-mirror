import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from psynet.sqlalchemy_profiling import (
    _parse_bool,
    _parse_env_settings,
    assert_query_count,
    sqlalchemy_profile,
)

Base = declarative_base()


class Widget(Base):
    __tablename__ = "widget"

    id = Column(Integer, primary_key=True)
    name = Column(String)


def make_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


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


def test_sqlalchemy_profile_filters_by_min_duration():
    engine = create_engine("sqlite:///:memory:")
    with sqlalchemy_profile(engine, min_duration_ms=1e9) as profiler:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))

    assert profiler.total_count == 0
    assert profiler.get_stats() == []
    assert "No queries captured." in profiler.format_summary()


def test_sqlalchemy_profile_normalizes_statements():
    engine = create_engine("sqlite:///:memory:")
    with sqlalchemy_profile(engine, normalize_sql=True) as profiler:
        with engine.begin() as conn:
            conn.execute(text("SELECT  1"))
            conn.execute(text("SELECT\t1"))

    stats = profiler.get_stats()
    assert len(stats) == 1
    assert stats[0].statement == "SELECT 1"
    assert stats[0].count == 2


def test_sqlalchemy_profile_truncates_statements():
    engine = create_engine("sqlite:///:memory:")
    long_number = "1" * 50
    statement = f"SELECT {long_number}"
    max_chars = 20
    with sqlalchemy_profile(engine, max_statement_chars=max_chars) as profiler:
        with engine.begin() as conn:
            conn.execute(text(statement))

    stats = profiler.get_stats()
    assert len(stats) == 1
    assert stats[0].statement.endswith("...")
    assert len(stats[0].statement) == max_chars


def test_sqlalchemy_profile_captures_stack():
    engine = create_engine("sqlite:///:memory:")
    with sqlalchemy_profile(engine, capture_stack=True, stack_depth=2) as profiler:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))

    stats = profiler.get_stats()
    assert len(stats) == 1
    assert stats[0].stack is not None
    assert 1 <= len(stats[0].stack) <= 2
    assert all("/sqlalchemy/" not in frame for frame in stats[0].stack)
    assert all("sqlalchemy_profiling.py" not in frame for frame in stats[0].stack)


def test_sqlalchemy_profile_reset_clears_stats():
    engine = create_engine("sqlite:///:memory:")
    with sqlalchemy_profile(engine) as profiler:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT 1"))

    profiler.reset()
    assert profiler.total_count == 0
    assert profiler.get_stats() == []


def test_get_stats_sorted_by_count():
    engine = create_engine("sqlite:///:memory:")
    with sqlalchemy_profile(engine) as profiler:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT 2"))

    stats = profiler.get_stats(sort_by="count")
    assert stats[0].statement == "SELECT 1"
    assert stats[0].count >= stats[1].count


def test_commit_profile_classifies_types():
    engine, SessionLocal = make_session_factory()
    with sqlalchemy_profile(engine) as profiler:
        session = SessionLocal()
        widget = Widget(name="alpha")
        session.add(widget)
        session.commit()

        widget.name = "beta"
        session.commit()

        other = Widget(name="gamma")
        session.add(other)
        widget.name = "delta"
        session.commit()

        session.delete(other)
        session.commit()

        session.execute(text("SELECT 1"))
        session.commit()
        session.close()

    commit_types = {stat.commit_type for stat in profiler.get_commit_stats()}
    assert "insert" in commit_types
    assert "update" in commit_types
    assert "insert+update" in commit_types
    assert "delete" in commit_types
    assert "no-op" in commit_types
    assert profiler.commit_total_count >= 5
    assert profiler.commit_total_time_ms >= 0.0


def test_assert_query_count_raises_when_exceeded():
    engine = create_engine("sqlite:///:memory:")
    with pytest.raises(AssertionError, match="Expected between 0 and 1 queries"):
        with assert_query_count(max_queries=1, engine=engine):
            with engine.begin() as conn:
                conn.execute(text("SELECT 1"))
                conn.execute(text("SELECT 1"))


def test_assert_query_count_raises_when_below_minimum():
    engine = create_engine("sqlite:///:memory:")
    with pytest.raises(AssertionError, match="Expected between 1 and 2 queries"):
        with assert_query_count(max_queries=2, min_queries=1, engine=engine):
            pass


def test_parse_env_settings_and_bool():
    assert _parse_env_settings(None) == {"enabled": False, "options": {}}
    assert _parse_env_settings("") == {"enabled": False, "options": {}}
    assert _parse_env_settings("0") == {"enabled": False, "options": {}}

    settings = _parse_env_settings("min_ms=50,top_n=5,stack=1")
    assert settings["enabled"] is True
    assert settings["options"] == {"min_ms": "50", "top_n": "5", "stack": "1"}

    assert _parse_bool("0") is False
    assert _parse_bool("false") is False
    assert _parse_bool("off") is False
    assert _parse_bool("1") is True
    assert _parse_bool("true") is True
