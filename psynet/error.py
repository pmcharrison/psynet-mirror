from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from psynet.data import SQLBase, SQLMixin, register_table


@register_table
class ErrorRecord(SQLBase, SQLMixin):
    __tablename__ = "error"
    __extra_vars__ = {}

    # Remove default SQL columns
    failed = None
    failed_reason = None
    time_of_death = None

    token = Column(String)
    kind = Column(String)
    message = Column(String)
    traceback = Column(String)

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant", back_populates="errors"
    )

    worker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"), index=True)
    network = relationship("TrialNetwork", back_populates="errors")

    node_id = Column(Integer, ForeignKey("node.id"), index=True)
    node = relationship("TrialNode", back_populates="errors")

    response_id = Column(Integer, ForeignKey("response.id"), index=True)
    response = relationship("psynet.timeline.Response", back_populates="errors")

    trial_id = Column(Integer, ForeignKey("info.id"), index=True)
    trial = relationship("psynet.trial.main.Trial", back_populates="errors")

    response_id = Column(Integer, ForeignKey("response.id"), index=True)
    response = relationship("psynet.timeline.Response", back_populates="errors")

    asset_key = Column(String, ForeignKey("asset.key"), index=True)
    asset = relationship("Asset", back_populates="errors")

    process_id = Column(Integer, ForeignKey("process.id"), index=True)
    process = relationship("AsyncProcess", back_populates="errors")

    def __init__(self, error, **kwargs):
        super().__init__(message=str(error), kind=type(error).__name__, **kwargs)

        if self.participant:
            self.worker_id = self.participant.worker_id
