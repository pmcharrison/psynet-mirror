from flask import render_template
from sqlalchemy.orm import joinedload

from psynet.participant import Participant
from psynet.sync import (
    Grouper,
    ParticipantLinkBarrier,
    ParticipantLinkSyncGroup,
    SimpleSyncGroup,
    SyncGroup,
)

TEMPLATE_NAME = "dashboard_sync_groups.html"


def _get_grouper_progress():
    """
    Return list of dicts describing each Grouper in the timeline and how many
    participants are currently waiting at it. Used for the "Grouper progress" table.
    """
    try:
        from psynet.experiment import get_experiment

        exp = get_experiment()
    except Exception:
        return [], {}

    groupers = (
        {}
    )  # barrier_id -> {barrier_id, group_type, batch_size?, initial_group_size?}

    def visit(elts):
        if elts is None:
            return
        for elt in list(elts) if isinstance(elts, (list, tuple)) else [elts]:
            if elt is None:
                continue
            links = getattr(elt, "links", None) or {}
            barrier = links.get("barrier")
            if isinstance(barrier, Grouper) and barrier.id not in groupers:
                row = {
                    "barrier_id": barrier.id,
                    "group_type": barrier.group_type,
                    "batch_size": getattr(barrier, "batch_size", None),
                    "initial_group_size": getattr(barrier, "initial_group_size", None),
                }
                groupers[barrier.id] = row
            if hasattr(elt, "elts") and elt.elts is not None:
                visit(elt.elts)

    for branch_elts in exp.timeline.elts.values():
        visit(branch_elts)

    return list(groupers.values())


def _get_waiting_by_participant_and_barrier():
    """Return list of (participant_id, barrier_id) for all participants currently waiting at a barrier."""
    return (
        ParticipantLinkBarrier.query.join(Participant)
        .filter(
            ~ParticipantLinkBarrier.released,
            ~Participant.failed,
            Participant.status == "working",
        )
        .with_entities(
            ParticipantLinkBarrier.participant_id,
            ParticipantLinkBarrier.barrier_id,
        )
        .all()
    )


def report_sync_groups():
    """Render the sync groups dashboard page with active and recent sync groups."""
    grouper_configs = _get_grouper_progress()

    groups = (
        SyncGroup.query.options(
            joinedload(SyncGroup.participant_links).joinedload(
                ParticipantLinkSyncGroup.participant
            ),
            joinedload(SyncGroup.leader),
        )
        .order_by(SyncGroup.id.desc())
        .limit(500)
        .all()
    )

    waiting_links = _get_waiting_by_participant_and_barrier()
    # participant_id -> list of barrier_ids they are waiting at
    waiting_by_participant = {}
    # barrier_id -> (count, sorted list of participant ids)
    waiting_by_barrier = {}
    for pid, barrier_id in waiting_links:
        waiting_by_participant.setdefault(pid, []).append(barrier_id)
        if barrier_id not in waiting_by_barrier:
            waiting_by_barrier[barrier_id] = ([], [])
        waiting_by_barrier[barrier_id][1].append(pid)
    for bid in waiting_by_barrier:
        lst = waiting_by_barrier[bid][1]
        waiting_by_barrier[bid] = (len(lst), sorted(lst))

    group_rows = []
    for group in groups:
        participant_ids = {p.id for p in group.participants}
        # barrier_id -> count and list of participants in this group waiting at it
        barrier_counts = {}
        barrier_participant_ids = {}
        for pid in participant_ids:
            for barrier_id in waiting_by_participant.get(pid, []):
                barrier_counts[barrier_id] = barrier_counts.get(barrier_id, 0) + 1
                barrier_participant_ids.setdefault(barrier_id, []).append(pid)
        waiting_at_barriers = [
            {
                "barrier_id": bid,
                "waiting_count": c,
                "participant_ids": sorted(barrier_participant_ids.get(bid, [])),
            }
            for bid, c in sorted(barrier_counts.items())
        ]

        participants_with_status = sorted(
            [
                {
                    "id": p.id,
                    "failed": p.failed,
                    "status": getattr(p, "status", None) or "—",
                    "failed_reason": (
                        ", ".join(p.failure_tags)
                        if getattr(p, "failure_tags", None)
                        else None
                    ),
                }
                for p in group.participants
            ],
            key=lambda x: x["id"],
        )
        row = {
            "id": group.id,
            "group_type": group.group_type or "—",
            "active": group.active,
            "n_active_participants": group.n_active_participants,
            "leader_id": group.leader_id,
            "leader_worker_id": group.leader.worker_id if group.leader else "—",
            "end_time": group.end_time,
            "last_barrier_pass_time": group.last_barrier_pass_time,
            "participants": participants_with_status,
            "waiting_at_barriers": waiting_at_barriers,
        }
        if isinstance(group, SimpleSyncGroup):
            row["min_group_size"] = group.min_group_size
            row["max_group_size"] = group.max_group_size
            row["initial_group_size"] = group.initial_group_size
            row["accepts_top_ups"] = group.accepts_top_ups
        else:
            row["min_group_size"] = None
            row["max_group_size"] = None
            row["initial_group_size"] = None
            row["accepts_top_ups"] = None
        group_rows.append(row)

    has_simple_groups = any(r["min_group_size"] is not None for r in group_rows)

    grouper_progress = []
    for cfg in grouper_configs:
        bid = cfg["barrier_id"]
        count, pids = waiting_by_barrier.get(bid, (0, []))
        grouper_progress.append(
            {
                "barrier_id": bid,
                "group_type": cfg["group_type"],
                "batch_size": cfg.get("batch_size"),
                "initial_group_size": cfg.get("initial_group_size"),
                "waiting_count": count,
                "participant_ids": pids,
            }
        )

    return render_template(
        TEMPLATE_NAME,
        title="Sync groups",
        groups=group_rows,
        has_simple_groups=has_simple_groups,
        grouper_progress=grouper_progress,
    )
