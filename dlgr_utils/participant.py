from dallinger.models import Participant
from . import field
from sqlalchemy.ext.hybrid import hybrid_property
import rpdb

class UndefinedVariableError(Exception):
    pass

class VarStore:
    def __init__(self, participant):
        self._participant = participant

    def __getattr__(self, name):
        participant = self.__dict__["_participant"]
        if name is "_participant":
            return participant
        else:
            try:
                return participant.details[name]
            except KeyError:
                raise UndefinedVariableError(f"Undefined variable: {name}.")

    def __setattr__(self, name, value):
        if name is "_participant":
            self.__dict__["_participant"] = value
        else:
            # We need to copy the dictionary otherwise
            # SQLAlchemy won't notice that we changed it.
            all_vars = self.__dict__["_participant"].details.copy()
            all_vars[name] = value
            self.__dict__["_participant"].details = all_vars


@property
def var(self):
    return VarStore(self)

@property 
def initialised(self):
    return self.elt_id is not None

def _set_var(self, name, value):
    self.var.__setattr__(name, value)

Participant.var = var
Participant.set_var = _set_var
Participant.elt_id = field.claim_field(1, int)
Participant.page_uuid = field.claim_field(2, str)
Participant.complete = field.claim_field(3, bool)
Participant.answer = field.claim_field(4, object)
Participant.initialised = initialised

def get_participant(participant_id):
    return Participant.query.get(participant_id)
