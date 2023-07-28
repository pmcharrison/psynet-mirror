import random
from math import floor
from typing import Callable, List, Optional

from dallinger import db
from dallinger.models import timenow
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relationship

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.page import WaitPage
from psynet.participant import Participant
from psynet.timeline import CodeBlock
from psynet.utils import call_function


class Barrier:
    """
    A barrier is a timeline construct that holds participants in a waiting area until certain conditions
    are satisfied to release them. The decision about which participants to release at any given point is taken by
    the ``choose_who_to_release`` method, which the user is expected to provide.

    Parameters
    ----------

    id_
        ID parameter for the barrier. Barriers with the same ID share waiting areas; this allows participants
        at different points in the timeline to share the same waiting areas.

    waiting_logic
        Either a single timeline element or a list of timeline elements (created by ``join``) that is to be displayed
        to the participant while they are waiting at the barrier. If left at the default value of ``None``
        then the participant will be shown a default waiting page.

    waiting_logic_expected_repetitions
        The number of times that the participant is expected to experience the waiting_logic during a given barrier
        visit. This is used for time estimation.

    max_wait_time
        The maximum amount of time in seconds that the participant will be allowed to wait at the barrier;
        if this time is exceeded and the participant is still not released, then the participant will be failed
        and sent to the end of the experiment.

    fix_time_credit
        If set to ``True``, then the amount of time 'credit' that the participant receives will be capped
        according to the estimate derived from ``waiting_logic`` and ``waiting_logic_expected_repetitions``.
    """

    def __init__(
        self,
        id_: str,
        waiting_logic=None,
        waiting_logic_expected_repetitions=3,
        max_wait_time=20,
        fix_time_credit=False,
    ):
        if waiting_logic is None:
            waiting_logic = WaitPage(wait_time=2)

        self.id = id_
        self.waiting_logic = waiting_logic
        self.waiting_logic_expected_repetitions = waiting_logic_expected_repetitions
        self.max_wait_time = max_wait_time
        self.fix_time_credit = fix_time_credit

    def choose_who_to_release(
        self, waiting_participants: List[Participant]
    ) -> List[Participant]:
        """
        Given a list of waiting participants, decides which of these participants should be released
        from the barrier.

        Parameters
        ----------
        waiting_participants
            A list of waiting participants.

        Returns
        -------

        A list of participants to be released.
        """
        raise NotImplementedError

    def resolve(self):
        from psynet.timeline import join, while_loop

        return join(
            CodeBlock(lambda participant: self.receive_participant(participant)),
            while_loop(
                label=f"barrier:{self.id}",
                condition=lambda participant: not self.can_participant_exit(
                    participant
                ),
                logic=self.waiting_logic,
                expected_repetitions=self.waiting_logic_expected_repetitions,
                max_loop_time=self.max_wait_time,
                fix_time_credit=self.fix_time_credit,
            ),
        )

    def receive_participant(self, participant: Participant):
        link = ParticipantLinkBarrier(participant=participant, barrier_id=self.id)
        link.arrival_time = timenow()
        db.session.add(link)

    def get_participant_link(self, participant: Participant):
        return (
            db.session.query(ParticipantLinkBarrier)
            .filter(
                ~ParticipantLinkBarrier.released,
                ParticipantLinkBarrier.participant_id == participant.id,
            )
            .one_or_none()
        )

    def _get_waiting_participants(self):
        return self.get_waiting_participants(barrier_id=self.id)

    @classmethod
    def get_waiting_participants(cls, barrier_id: str) -> List[Participant]:
        """
        Gets the participants currently waiting at a barrier.

        Parameters
        ----------
        barrier_id
            The ID of the barrier to check.

        Returns
        -------

        A list of waiting participants. Note that this only includes currently active participants
        (not participants who failed and left the experiment).
        """
        return (
            db.session.query(Participant)
            .join(ParticipantLinkBarrier)
            .filter(
                ParticipantLinkBarrier.barrier_id == barrier_id,
                ~ParticipantLinkBarrier.released,
                ~Participant.failed,
                Participant.status == "working",
            )
            .all()
        )

    def release(self, participant: Participant):
        # Note: this currently emits one SQL query per participant; this could be optimized
        link = self.get_participant_link(participant)
        if link is None:
            raise RuntimeError(
                "Could not find an appropriate barrier link to release the participant from "
                f"(participant_id = {participant.id}, barrier_id = '{self.id}')."
            )
        link.release()

    def can_participant_exit(self, participant: "Participant"):
        self.process_potential_releases()
        barrier_is_active = self.id in participant.active_barriers
        return not barrier_is_active

    def process_potential_releases(self):
        waiting_participants = self._get_waiting_participants()
        participants_to_release = self.choose_who_to_release(waiting_participants)

        for participant in participants_to_release:
            self.release(participant)

        db.session.commit()


class GroupBarrier(Barrier):
    """
    A GroupBarrier is a Barrier that waits until all participants in a given :class:`~psynet.sync.SyncGroup`
    have reached the Barrier.

    Parameters
    ----------

    id_
        ID parameter for the Barrier. Barriers with the same ID share waiting areas; this allows participants
        at different points in the timeline to share the same waiting areas.

    group_type
        Identifies the kind of groups that the Barrier is operating over (see :class:`~psynet.sync.Grouper`).

    waiting_logic
        Either a single timeline element or a list of timeline elements (created by ``join``) that is to be displayed
        to the participant while they are waiting at the barrier. If left at the default value of ``None``
        then the participant will be shown a default waiting page.

    waiting_logic_expected_repetitions
        The number of times that the participant is expected to experience the waiting_logic during a given barrier
        visit. This is used for time estimation.

    max_wait_time
        The maximum amount of time in seconds that the participant will be allowed to wait at the barrier;
        if this time is exceeded and the participant is still not released, then the participant will be failed
        and sent to the end of the experiment.

    fix_time_credit
        If set to ``True``, then the amount of time 'credit' that the participant receives will be capped
        according to the estimate derived from ``waiting_logic`` and ``waiting_logic_expected_repetitions``.
    """

    def __init__(
        self,
        id_: str,
        group_type: str,
        waiting_logic=None,
        waiting_logic_expected_repetitions=3,
        max_wait_time=20,
        on_release: Optional[Callable] = None,
        fix_time_credit=True,
    ):
        super().__init__(
            id_=id_,
            waiting_logic=waiting_logic,
            waiting_logic_expected_repetitions=waiting_logic_expected_repetitions,
            max_wait_time=max_wait_time,
            fix_time_credit=fix_time_credit,
        )
        self.group_type = group_type
        self.on_release = on_release

    def choose_who_to_release(self, waiting_participants: List[Participant]):
        waiting_participant_ids = [p.id for p in waiting_participants]
        participants_to_release = []

        groups = {
            participant.active_sync_groups[
                self.group_type
            ].id: participant.active_sync_groups[self.group_type]
            for participant in waiting_participants
        }

        for group in groups.values():
            all_participants_present = all(
                [
                    participant.id in waiting_participant_ids
                    for participant in group.participants
                ]
            )
            if all_participants_present:
                for participant in group.participants:
                    participants_to_release.append(participant)

                if self.on_release:
                    call_function(
                        self.on_release, group=group, participants=group.participants
                    )

        return participants_to_release


class Grouper(Barrier):
    """
    A Grouper is a kind of Barrier that assigns incoming participants into groups.
    This is a generic class that requires several methods to be overrun, in particular
    ``ready_to_group`` and ``group``.

    Parameters
    ----------

    group_type
        A textual label for the groups that are created. This label is used to link the Grouper with
        subsequent GroupBarriers.

    id
        Optional ID parameter for this grouper. If left blank the default value is ``group_type + "_" + "grouper"``.
        Groupers with the same ID are treated as equivalent and share the same participant waiting areas.

    waiting_logic
        Either a single timeline element or a list of timeline elements (created by ``join``) that is to be displayed
        to the participant while they are waiting at the barrier. If left at the default value of ``None``
        then the participant will be shown a default waiting page.

    waiting_logic_expected_repetitions
        The number of times that the participant is expected to experience the waiting_logic during a given barrier
        visit. This is used for time estimation.

    max_wait_time
        The maximum amount of time in seconds that the participant will be allowed to wait at the barrier;
        if this time is exceeded and the participant is still not released, then the participant will be failed
        and sent to the end of the experiment.
    """

    def __init__(
        self,
        group_type: str,
        id_: Optional[str] = None,
        waiting_logic=None,
        waiting_logic_expected_repetitions=3,
        max_wait_time=20,
    ):
        if not id_:
            id_ = group_type + "_" + "grouper"
        super().__init__(
            id_=id_,
            waiting_logic=waiting_logic,
            waiting_logic_expected_repetitions=waiting_logic_expected_repetitions,
            max_wait_time=max_wait_time,
        )
        self.group_type = group_type

    def ready_to_group(self, participants: List[Participant]) -> bool:
        """
        Determines whether the Grouper is ready to group a given collection of participants.
        Note that not all participants need to be grouped at once; it's permissible to
        leave some participants still waiting.

        Parameters
        ----------

        participants
            List of participants who are candidates for grouping.

        Returns
        -------

        ``True`` if the grouper is ready to group (some of) the participants, ``False`` otherwise.

        """
        raise NotImplementedError

    def group(self, participants: List[Participant]) -> List["SyncGroup"]:
        """
        This method is run if ``ready_to_group`` returns ``True``.
        It is responsible for grouping participants.

        Parameters
        ----------
        participants
            Participants who are candidates for grouping.

        Returns
        -------
        A list of SyncGroups who should be populated by the grouped participants.
        """
        raise NotImplementedError

    def receive_participant(self, participant: Participant):
        if self.group_type in participant.active_sync_groups:
            raise RuntimeError(
                f"Participant is already in a group with this group_type ('{self.group_type}'). "
                "You should close this group, typically by including a GroupCloser in the timeline, "
                "before reassigning it."
            )
        super().receive_participant(participant)

    def choose_who_to_release(self, waiting_participants: List[Participant]):
        participants_to_release = []

        if self.ready_to_group(waiting_participants):
            groups = self.group(waiting_participants)

            if not isinstance(groups, list) and all(
                [isinstance(group, SyncGroup) for group in groups]
            ):
                raise ValueError("group() must return a list of SyncGroups.")

            for _group in groups:
                db.session.add(_group)
                for _participant in _group.participants:
                    participants_to_release.append(_participant)

            db.session.commit()

        return participants_to_release

    def select_leader(self, participants: List[Participant]) -> Participant:
        """
        By default the leader is randomly chosen from the list of available participants.

        Parameters
        ----------

        participants
            Participants to choose from.

        Returns
        -------

        A participant to be assigned 'leader' of the SyncGroup.

        """
        return random.choice(participants)


class SimpleGrouper(Grouper):
    """
    A Simple Grouper waits until ``batch_size`` many participants are waiting,
    and then randomly partitions this group of participants into groups of size ``group_size``.

    Parameters
    ----------

    group_type
        A textual label for the groups that are created. This label is used to link the Grouper with
        subsequent GroupBarriers.

    group_size
        Size of the groups to create.

    batch_size
        Number of participants that should be waiting until the groups are created.

    kwargs
        Further arguments to pass to Grouper.
    """

    def __init__(
        self,
        group_type: str,
        group_size: int,
        batch_size: int = None,
        **kwargs,
    ):
        super().__init__(group_type=group_type, **kwargs)
        self.group_size = group_size
        self.batch_size = batch_size

    def ready_to_group(self, participants: List[Participant]) -> bool:
        if self.batch_size:
            quorum = self.batch_size
        else:
            quorum = self.group_size
        return len(participants) >= quorum

    def group(self, participants: List[Participant]) -> List["SyncGroup"]:
        n_groups = floor(len(participants) / self.group_size)
        n_participants_to_group = n_groups * self.group_size
        participants_to_group = participants[:n_participants_to_group]

        grouped_participants = self.randomly_partition_list(
            participants_to_group, group_size=self.group_size
        )
        groups = []
        for _participants in grouped_participants:
            _group = SyncGroup(group_type=self.group_type)
            groups.append(_group)

            for _participant in _participants:
                _group.participants.append(_participant)

            _group.leader = self.select_leader(_participants)

        return groups

    @staticmethod
    def randomly_partition_list(lst: list, group_size: int):
        n_groups = len(lst) / group_size
        if not n_groups == floor(n_groups):
            raise ValueError(
                f"List size ({len(lst)}) is not an integer multiple of group_size ({group_size})"
            )
        n_groups = floor(n_groups)
        lst = lst.copy()
        random.shuffle(lst)
        return [lst[i::n_groups] for i in range(n_groups)]


@register_table
class SyncGroup(SQLBase, SQLMixin):
    """
    A SyncGroup represents a group of participants that are synchronized at various points in the experiment.
    Such groups are created by Groupers and synchronized by GroupBarriers.

    Attributes
    ----------

    leader : Participant
        The leader of the SyncGroup. This can be reassigned by logic such as ``group.leader = participant``.

    participants : List[Participant]
        A list of participants in that group. Additional participants can be added by logic such as
        ``group.participants.append(participant)``.
    """

    __tablename__ = "sync_group"

    group_type = Column(String)
    active = Column(Boolean, default=True)
    end_time = Column(DateTime)
    leader_id = Column(Integer, ForeignKey("participant.id"))

    participant_links = relationship(
        "ParticipantLinkSyncGroup",
        cascade="all, delete-orphan",
    )

    participants = association_proxy(
        "participant_links",
        "participant",
        creator=lambda participant: ParticipantLinkSyncGroup(participant=participant),
    )

    leader = relationship(
        "psynet.participant.Participant",
        cascade="all",
    )

    def add_participant(self, participant: Participant):
        link = ParticipantLinkSyncGroup(
            participant=participant,
            sync_group=self,
        )
        db.session.add(link)

    @classmethod
    def get_active_group(
        cls,
        participant: Participant,
        group_type: str,
    ) -> "SyncGroup":
        return participant.active_sync_groups[group_type]

    def close(self):
        self.active = False
        self.end_time = timenow()


@register_table
class ParticipantLinkSyncGroup(SQLBase, SQLMixin):
    __tablename__ = "participant_link_sync_group"

    arrival_time = Column(DateTime)

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant", back_populates="sync_group_links"
    )

    sync_group_id = Column(Integer, ForeignKey("sync_group.id"), index=True)
    sync_group = relationship("SyncGroup", back_populates="participant_links")


@register_table
class ParticipantLinkBarrier(SQLBase, SQLMixin):
    __tablename__ = "participant_link_barrier"

    barrier_id = Column(String, index=True)
    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant",
        backref=backref(
            "barrier_links", cascade="all, delete-orphan"
        ),  # for some reason backpopulates didn't work here
    )

    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    released = Column(Boolean, default=False)

    def release(self):
        self.departure_time = timenow()
        self.released = True

    def get_waiting_participants(self):
        return Barrier.get_waiting_participants(self.barrier_id)


Participant.sync_group_links = relationship(
    "ParticipantLinkSyncGroup",
    cascade="all, delete-orphan",
)

Participant.sync_groups = association_proxy(
    "sync_group_links",
    "sync_group",
)

# No association proxy for barrier links because barriers aren't represented as database objects (yet)


class GroupCloser(GroupBarrier):
    """
    A timeline construct for closing a previously created group.
    This is required before creating a new group with the same ``group_type``.
    """

    def __init__(self, group_type: str, **kwargs):
        if "id_" not in kwargs:
            kwargs["id_"] = f"closer_{group_type}"

        super().__init__(
            group_type=group_type, on_release=lambda group: group.close(), **kwargs
        )
