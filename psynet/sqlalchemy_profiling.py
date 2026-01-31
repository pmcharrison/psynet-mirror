import atexit
import os
import threading
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import event
from sqlalchemy.engine import Engine

_AUTO_PROFILER = None


@dataclass
class QueryStats:
    statement: str
    stack: Optional[Tuple[str, ...]]
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    def add(self, duration_ms: float) -> None:
        self.count += 1
        self.total_ms += duration_ms
        if self.count == 1:
            self.min_ms = duration_ms
        else:
            self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

    @property
    def mean_ms(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total_ms / self.count


class SQLAlchemyQueryProfiler:
    """
    Collect timing statistics for SQLAlchemy statements.

    Parameters
    ----------
    engine :
        SQLAlchemy engine to attach to.
    capture_stack : bool, optional
        Whether to capture stack traces and group by them.
    stack_depth : int, optional
        Maximum number of frames to keep when capturing stacks.
    min_duration_ms : float, optional
        Minimum duration in milliseconds for a statement to be recorded.
    normalize_sql : bool, optional
        Whether to collapse whitespace in statements.
    max_statement_chars : int, optional
        Maximum statement length to retain before truncation.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        capture_stack: bool = False,
        stack_depth: int = 6,
        min_duration_ms: float = 0.0,
        normalize_sql: bool = True,
        max_statement_chars: Optional[int] = None,
    ) -> None:
        self.engine = engine
        self._capture_stack = capture_stack
        self._stack_depth = stack_depth
        self._min_duration_ms = min_duration_ms
        self._normalize_sql = normalize_sql
        self._max_statement_chars = max_statement_chars
        self._stats: Dict[Tuple[str, Optional[Tuple[str, ...]]], QueryStats] = {}
        self._total_count = 0
        self._total_time_ms = 0.0
        self._started = False
        self._lock = threading.Lock()

    def __enter__(self) -> "SQLAlchemyQueryProfiler":
        self.start()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.stop()

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def total_time_ms(self) -> float:
        return self._total_time_ms

    def start(self) -> None:
        if self._started:
            return
        event.listen(self.engine, "before_cursor_execute", self._before_cursor_execute)
        event.listen(self.engine, "after_cursor_execute", self._after_cursor_execute)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        event.remove(self.engine, "before_cursor_execute", self._before_cursor_execute)
        event.remove(self.engine, "after_cursor_execute", self._after_cursor_execute)
        self._started = False

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()
            self._total_count = 0
            self._total_time_ms = 0.0

    def get_stats(
        self,
        *,
        top_n: Optional[int] = None,
        sort_by: str = "total_ms",
        min_total_ms: Optional[float] = None,
        min_count: int = 1,
    ) -> List[QueryStats]:
        stats = [
            stat
            for stat in self._stats.values()
            if stat.count >= min_count
            and (min_total_ms is None or stat.total_ms >= min_total_ms)
        ]
        sort_key = _sort_key(sort_by)
        stats.sort(key=sort_key, reverse=True)
        if top_n is not None:
            stats = stats[:top_n]
        return stats

    def format_summary(
        self,
        *,
        top_n: int = 20,
        sort_by: str = "total_ms",
        min_total_ms: Optional[float] = None,
        min_count: int = 1,
    ) -> str:
        stats = self.get_stats(
            top_n=top_n,
            sort_by=sort_by,
            min_total_ms=min_total_ms,
            min_count=min_count,
        )
        lines = [
            "SQLAlchemy query profile: "
            f"{self.total_count} queries, {self.total_time_ms:.2f} ms"
        ]
        if not stats:
            lines.append("No queries captured.")
            return "\n".join(lines)

        lines.append("count total_ms mean_ms  max_ms statement")
        for stat in stats:
            lines.append(
                f"{stat.count:5d} "
                f"{stat.total_ms:8.2f} "
                f"{stat.mean_ms:7.2f} "
                f"{stat.max_ms:7.2f} "
                f"{stat.statement}"
            )
            if stat.stack:
                lines.extend([f"      at {frame}" for frame in stat.stack])
        return "\n".join(lines)

    def print_summary(self, **kwargs) -> None:
        print(self.format_summary(**kwargs))

    def _before_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ) -> None:
        if context is None:
            return
        context._psynet_query_start_time = perf_counter()
        if self._capture_stack:
            context._psynet_query_stack = _build_stack(self._stack_depth)

    def _after_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ) -> None:
        if context is None:
            return
        start_time = getattr(context, "_psynet_query_start_time", None)
        if start_time is None:
            return
        duration_ms = (perf_counter() - start_time) * 1000.0
        if duration_ms < self._min_duration_ms:
            return
        statement_text = _format_statement(
            statement, self._normalize_sql, self._max_statement_chars
        )
        stack = (
            getattr(context, "_psynet_query_stack", None)
            if self._capture_stack
            else None
        )
        key = (statement_text, stack)
        with self._lock:
            stat = self._stats.get(key)
            if stat is None:
                stat = QueryStats(statement=statement_text, stack=stack)
                self._stats[key] = stat
            stat.add(duration_ms)
            self._total_count += 1
            self._total_time_ms += duration_ms


@contextmanager
def sqlalchemy_profile(engine: Engine, **kwargs) -> Iterable[SQLAlchemyQueryProfiler]:
    """
    Profile SQLAlchemy statements executed against an engine.

    Parameters
    ----------
    engine :
        SQLAlchemy engine to attach to.
    **kwargs
        Keyword arguments forwarded to ``SQLAlchemyQueryProfiler``.

    Yields
    ------
    SQLAlchemyQueryProfiler
        The active profiler instance.
    """
    profiler = SQLAlchemyQueryProfiler(engine, **kwargs)
    profiler.start()
    try:
        yield profiler
    finally:
        profiler.stop()


@contextmanager
def assert_query_count(
    max_queries: int,
    *,
    min_queries: int = 0,
    engine: Optional[Engine] = None,
    **profiler_kwargs,
) -> Iterable[SQLAlchemyQueryProfiler]:
    """
    Assert a query count budget within a block.

    Parameters
    ----------
    max_queries :
        Maximum number of SQL statements allowed.
    min_queries :
        Minimum number of SQL statements expected.
    engine :
        SQLAlchemy engine to attach to. Defaults to Dallinger's engine.
    **profiler_kwargs
        Keyword arguments forwarded to ``SQLAlchemyQueryProfiler``.

    Yields
    ------
    SQLAlchemyQueryProfiler
        The active profiler instance.
    """
    if engine is None:
        from dallinger import db

        engine = db.engine
    with sqlalchemy_profile(engine, **profiler_kwargs) as profiler:
        yield profiler
    if profiler.total_count < min_queries or profiler.total_count > max_queries:
        raise AssertionError(
            f"Expected between {min_queries} and {max_queries} queries, "
            f"but saw {profiler.total_count}."
        )


def get_active_sqlalchemy_profiler() -> Optional[SQLAlchemyQueryProfiler]:
    """
    Return the profiler enabled by environment variables, if any.

    Returns
    -------
    SQLAlchemyQueryProfiler or None
        The active environment-configured profiler instance.
    """
    return _AUTO_PROFILER


def maybe_enable_sqlalchemy_profiling(
    engine: Optional[Engine] = None,
    *,
    env_var: str = "PSYNET_SQL_PROFILE",
) -> Optional[SQLAlchemyQueryProfiler]:
    """
    Enable SQLAlchemy profiling based on environment variables.

    Parameters
    ----------
    engine :
        SQLAlchemy engine to attach to. Defaults to Dallinger's engine.
    env_var :
        Environment variable that enables profiling. Set to a truthy value or
        a comma-separated list like ``min_ms=50,top_n=20,stack=1``.

    Returns
    -------
    SQLAlchemyQueryProfiler or None
        The active profiler instance if enabled.
    """
    value = os.getenv(env_var)
    settings = _parse_env_settings(value)
    if not settings["enabled"]:
        return None
    if engine is None:
        from dallinger import db

        engine = db.engine
    global _AUTO_PROFILER
    if _AUTO_PROFILER is not None:
        if _AUTO_PROFILER.engine is engine:
            return _AUTO_PROFILER
        _AUTO_PROFILER.stop()
        _AUTO_PROFILER = None
    options = settings["options"]
    min_duration_ms = float(options.get("min_ms", 0.0))
    top_n = int(options.get("top_n", 20))
    capture_stack = _parse_bool(options.get("stack", "0"))
    normalize_sql = _parse_bool(options.get("normalize", "1"))
    max_statement_chars = options.get("max_statement_chars")
    if max_statement_chars is not None:
        max_statement_chars = int(max_statement_chars)
    profiler = SQLAlchemyQueryProfiler(
        engine,
        capture_stack=capture_stack,
        min_duration_ms=min_duration_ms,
        normalize_sql=normalize_sql,
        max_statement_chars=max_statement_chars,
    )
    profiler.start()
    atexit.register(profiler.print_summary, top_n=top_n)
    _AUTO_PROFILER = profiler
    return profiler


def _build_stack(stack_depth: int) -> Optional[Tuple[str, ...]]:
    stack = traceback.extract_stack()
    filtered = []
    for frame in stack:
        filename = frame.filename.replace("\\", "/")
        if "/sqlalchemy/" in filename or filename.endswith("sqlalchemy_profiling.py"):
            continue
        filtered.append(frame)
    if stack_depth:
        filtered = filtered[-stack_depth:]
    if not filtered:
        return None
    return tuple(
        f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in filtered
    )


def _format_statement(
    statement: str,
    normalize_sql: bool,
    max_statement_chars: Optional[int],
) -> str:
    statement_text = str(statement)
    if normalize_sql:
        statement_text = " ".join(statement_text.split())
    if max_statement_chars and len(statement_text) > max_statement_chars:
        statement_text = statement_text[: max_statement_chars - 3] + "..."
    return statement_text


def _sort_key(sort_by: str):
    sort_by = sort_by.lower()
    if sort_by == "mean_ms":
        return lambda stat: stat.mean_ms
    if sort_by == "count":
        return lambda stat: stat.count
    if sort_by == "max_ms":
        return lambda stat: stat.max_ms
    return lambda stat: stat.total_ms


def _parse_bool(value: str) -> bool:
    value = value.strip().lower()
    return value not in {"0", "false", "no", "off", ""}


def _parse_env_settings(value: Optional[str]) -> Dict[str, object]:
    if value is None:
        return {"enabled": False, "options": {}}
    raw = value.strip()
    if raw == "":
        return {"enabled": False, "options": {}}
    enabled = raw.lower() not in {"0", "false", "no", "off"}
    options: Dict[str, str] = {}
    if "=" in raw:
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                options[part.lower()] = "true"
                continue
            key, val = part.split("=", 1)
            options[key.strip().lower()] = val.strip()
    return {"enabled": enabled, "options": options}
