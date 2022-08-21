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

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship(
        "psynet.participant.Participant", back_populates="errors"
    )

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("TrialNetwork", back_populates="errors")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship("TrialNode", back_populates="errors")

    response_id = Column(Integer, ForeignKey("response.id"))
    response = relationship("psynet.timeline.Response", back_populates="errors")

    trial_id = Column(Integer, ForeignKey("info.id"))
    trial = relationship("Trial", back_populates="errors")

    response_id = Column(Integer, ForeignKey("response.id"))
    response = relationship("psynet.timeline.Response", back_populates="errors")

    asset_key = Column(String, ForeignKey("asset.key"))
    asset = relationship("Asset", back_populates="errors")

    process_id = Column(Integer, ForeignKey("process.id"))
    process = relationship("AsyncProcess", back_populates="errors")

    def __init__(self, error, **kwargs):
        super().__init__(message=str(error), kind=type(error).__name__, **kwargs)
