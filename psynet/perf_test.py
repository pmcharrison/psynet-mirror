from tabulate import tabulate

from psynet.log import bold, error, success, warning


def colorize_success_rate(rate_str):
    if rate_str == "N/A":
        return rate_str
    pct = float(rate_str.rstrip("%"))
    if pct >= 100:
        return success(rate_str)
    elif pct > 0:
        return warning(rate_str)
    else:
        return error(rate_str)


def format_test_results(result):
    """Format detailed results after a single test completes. Returns list[str]."""
    lines = []

    def _fmt(value, suffix=""):
        return f"{value:.3f}{suffix}" if value is not None else "N/A"

    def _table_lines(rows, headers, indent="  ", min_label_width=28, **kwargs):
        kwargs.setdefault("tablefmt", "plain")
        if min_label_width and rows and not headers:
            rows = [[r[0].ljust(min_label_width)] + r[1:] for r in rows]
        table = tabulate(rows, headers=headers, **kwargs)
        for line in table.splitlines():
            lines.append(f"{indent}{line}")

    def _section(title):
        lines.append(bold(f"  {title}"))
        lines.append(f"  {'-' * 36}")

    bots_finished = max(
        result["completed_during_test"],
        result["bots_succeeded"] + result["bots_failed"],
    )

    total_started = result["total_bots_started"]
    if total_started > 0:
        completion_rate = f"{(bots_finished / total_started) * 100:.0f}%"
    else:
        completion_rate = "N/A"

    lines.append("")
    lines.append(success("\u2713 Test completed"))
    lines.append(bold(f"TEST RESULTS (n={result['n_bots']:,} bots)"))
    lines.append("")

    # BOT OUTCOMES
    _section("BOT OUTCOMES")
    bots_in_db = (
        result["bots_succeeded"] + result["bots_failed"] + result["bots_incomplete"]
    )
    bots_not_in_db = result["total_bots_started"] - bots_in_db
    outcome_rows = [
        ["Bots started", result["total_bots_started"]],
        ["Completed successfully", result["bots_succeeded"]],
        ["Completed with error", result["bots_failed"]],
        ["Timed out (still running)", result["bots_incomplete"]],
    ]
    if bots_not_in_db > 0:
        outcome_rows.append(["Never reached DB", bots_not_in_db])
    outcome_rows.append(["Completion rate", colorize_success_rate(completion_rate)])
    _table_lines(outcome_rows, headers=[], colalign=("left", "right"))
    lines.append("")

    # BOT RUNTIMES
    _section("BOT RUNTIMES")
    runtime_rows = []
    if result.get("actual_duration") is not None:
        runtime_rows.append(["Test duration", f"{result['actual_duration']:.1f}s"])
    if result.get("avg_bot_duration") is not None:
        runtime_rows.append(["Avg runtime", f"{result['avg_bot_duration']:.1f}s"])
    if result.get("avg_succeeded_duration") is not None:
        runtime_rows.append(
            [
                "Avg runtime (succeeded)",
                f"{result['avg_succeeded_duration']:.1f}s",
            ]
        )
    if result.get("avg_failed_duration") is not None:
        runtime_rows.append(
            [
                "Avg runtime (failed)",
                f"{result['avg_failed_duration']:.1f}s",
            ]
        )
    if result.get("avg_incomplete_duration") is not None:
        runtime_rows.append(
            [
                "Avg runtime (timed out)",
                f"{result['avg_incomplete_duration']:.1f}s",
            ]
        )
    if runtime_rows:
        _table_lines(runtime_rows, headers=[], colalign=("left", "right"))
    lines.append("")

    # Bot initialization time distribution (sub-section)
    init_times = result.get("initialization_times", [])
    if init_times:
        init_sorted = sorted(init_times)
        init_median = init_sorted[len(init_sorted) // 2]
        init_p95 = init_sorted[int(len(init_sorted) * 0.95)]
        init_max = init_sorted[-1]
        n_init = len(init_sorted)
        lines.append(bold(f"  BOT INIT TIMES (n={n_init}):"))
        lines.append(f"  {'-' * 36}")
        init_rows = [
            ["Median", f"{init_median:.3f}s"],
            ["95th percentile", f"{init_p95:.3f}s"],
            ["Max", f"{init_max:.3f}s"],
        ]
        _table_lines(
            init_rows,
            headers=[],
            colalign=("left", "right"),
        )
        lines.append("")

    # REQUEST METRICS
    _section("REQUEST METRICS")
    request_rows = [
        ["Total requests", result["total_requests"]],
        ["Request errors", result["request_errors"]],
    ]
    if result.get("requests_per_sec") is not None:
        request_rows.append(["Throughput", f"{result['requests_per_sec']:.2f} req/s"])
    _table_lines(request_rows, headers=[], colalign=("left", "right"))
    lines.append("")

    # RESPONSE TIMES
    n_req = result.get("total_requests", "?")
    _section(f"RESPONSE TIMES (n={n_req})")
    resp_rows = [
        ["Median", _fmt(result["median_response_time"], "s")],
        ["95th percentile", _fmt(result["p95_response_time"], "s")],
        ["99th percentile", _fmt(result["p99_response_time"], "s")],
        ["Max", _fmt(result["max_response_time"], "s")],
        ["Mean", _fmt(result["avg_response_time"], "s")],
        ["Std dev", _fmt(result["stddev_response_time"], "s")],
    ]
    _table_lines(resp_rows, headers=[], colalign=("left", "right"))
    lines.append("")

    # WAIT PAGE TIMES
    if result.get("median_wait_page_time") is not None:
        n_wait = result.get("n_wait_page_samples", "?")
        _section(f"WAIT PAGE TIMES (n={n_wait})")
        wait_rows = [
            ["Median", f"{result['median_wait_page_time']:.1f}s"],
            ["95th percentile", f"{result['p95_wait_page_time']:.1f}s"],
            ["Max", f"{result['max_wait_page_time']:.1f}s"],
        ]
        _table_lines(wait_rows, headers=[], colalign=("left", "right"))
        lines.append("")

    # TRIALS PER BOT
    n_succeeded = result.get("n_succeeded_bots", 0)
    _section(f"TRIALS PER BOT (n={n_succeeded} succeeded)")
    _tc = lambda k, fallback=0: (  # noqa: E731
        result[k] if result.get(k) is not None else fallback
    )
    trial_rows = [
        ["Min", _tc("min_trial_count")],
        ["Median", _tc("median_trial_count")],
        ["Max", _tc("max_trial_count")],
    ]
    _table_lines(trial_rows, headers=[], colalign=("left", "right"))
    lines.append("")

    # ASYNC PROCESS TIMES
    if result.get("process_stats"):
        n_procs = sum(ps["count"] for ps in result["process_stats"])
        _section(f"ASYNC PROCESS TIMES (n={n_procs})")
        _fmt = lambda v: f"{v:.3f}" if v is not None else "N/A"  # noqa: E731

        def _color_q_share(q_share, q_p95):
            if q_share is None or q_p95 is None:
                return "N/A"
            text = f"{q_share:.0%}"
            if q_share > 0.2 and q_p95 > 0.5:
                return error(text)
            if q_share > 0.2 and q_p95 > 0.2:
                return warning(text)
            return text

        proc_rows = [
            [
                ps["trial_maker_id"],
                ps["label"],
                ps["count"],
                f"{ps['avg']:.3f}",
                f"{ps['median']:.3f}",
                f"{ps['p95']:.3f}",
                f"{ps['max']:.3f}",
                _fmt(ps["q_avg"]),
                _fmt(ps["q_p95"]),
                _color_q_share(ps["q_share"], ps["q_p95"]),
            ]
            for ps in result["process_stats"]
        ]
        _table_lines(
            proc_rows,
            headers=[
                "Trial Maker",
                "Label",
                "Count",
                "Avg (s)",
                "Med (s)",
                "P95 (s)",
                "Max (s)",
                "Q Avg (s)",
                "Q P95 (s)",
                "Q Share",
            ],
            indent="    ",
            tablefmt="simple",
            colalign=(
                "left",
                "left",
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
            ),
        )
        lines.append("")
    else:
        _section("ASYNC PROCESS TIMES")
        lines.append("  No completed async processes.")
        lines.append("")

    return lines


def format_performance_summary(results):
    """Format cross-test comparison table. Returns list[str]."""
    lines = []

    def _fmt(value):
        return f"{value:.3f}" if value is not None else "N/A"

    show_scaling = len(results) > 1 and results[0].get("p95_response_time") is not None
    baseline_p95 = results[0].get("p95_response_time") if show_scaling else None
    baseline_q_p95 = results[0].get("q_delay_p95") if show_scaling else None

    summary_headers = [
        "|| Bots",
        "Succeeded",
        "Requests",
        "Req/s",
        "Resp P95 (s)",
    ]
    if show_scaling:
        summary_headers.append("vs base")
    summary_headers.append("Q P95 all (s)")
    if show_scaling:
        summary_headers.append("vs base")

    summary_rows = []
    for i, result in enumerate(results):
        p95 = result.get("p95_response_time")
        q_p95 = result.get("q_delay_p95")
        row = [
            result["n_bots"],
            result["bots_succeeded"],
            result["total_requests"],
            (
                f"{result['requests_per_sec']:.1f}"
                if result.get("requests_per_sec") is not None
                else "N/A"
            ),
            _fmt(p95),
        ]
        if show_scaling:
            if i == 0:
                row.append("\u2014")
            elif p95 is not None and baseline_p95 and baseline_p95 > 0:
                row.append(f"{p95 / baseline_p95:.1f}x")
            else:
                row.append("N/A")
        row.append(_fmt(q_p95))
        if show_scaling:
            if i == 0:
                row.append("\u2014")
            elif q_p95 is not None and baseline_q_p95 and baseline_q_p95 > 0:
                row.append(f"{q_p95 / baseline_q_p95:.1f}x")
            else:
                row.append("N/A")
        summary_rows.append(row)

    lines.append("")
    lines.append(bold("CUMULATIVE PERFORMANCE TEST SUMMARY"))
    lines.append("")
    table = tabulate(summary_rows, headers=summary_headers, tablefmt="simple")
    for line in table.splitlines():
        lines.append(f"  {line}")
    lines.append("")

    return lines
