from dallinger.models import Participant
from . import field
from sqlalchemy.ext.hybrid import hybrid_property
import rpdb

class VarStore:
    def __init__(self, participant):
        self._participant = participant

    def __getattr__(self, name):
        participant = self.__dict__["_participant"]
        if name is "_participant":
            return participant
        else:
            return participant.vars[name]

    def __setattr__(self, name, value):
        if name is "_participant":
            self.__dict__["_participant"] = value
        else:
            var_dict = self.__dict__["_participant"].vars
            var_dict[name] = value
            self.__dict__["_participant"].vars = var_dict

# old_init = Participant.__init__
# def new_init(
#     self,
#     recruiter_id,
#     worker_id,
#     assignment_id,
#     hit_id,
#     mode,
#     fingerprint_hash=None
#     ):
#     old_init(**locals())
#     assert False
#     self.var = VarStore(self)
# Participant.__init__ = new_init

# class Participant(dallinger.models.Participant):
#     __mapper_args__ = {"polymorphic_identity": "participant2"}

#     def __init__(
#         self,
#         recruiter_id,
#         worker_id,
#         assignment_id,
#         hit_id,
#         mode,
#         fingerprint_hash=None,
#     ):
#         super().__init__(**locals())
#         self.var = VarStore(self)

@property
def var(self):
    return VarStore(self)

@property 
def initialised(self):
    return self.elt_id is not None

Participant.var = var
Participant.elt_id = field.claim_field(1, int)
Participant.page_uuid = field.claim_field(1, str)
Participant.complete = field.claim_field(3, bool)
Participant.vars = field.claim_field(4, dict)
Participant.answer = field.claim_field(5, object)
Participant.initialised = initialised

def get_participant(participant_id):
    return Participant.query.get(participant_id)

# def _get_global(key):
#     raise NotImplementedError

# def _set_global(key, value):
#     raise NotImplementedError

# def _get_local(key):
#     raise NotImplementedError

# def _set_local(key, value):
#     raise NotImplementedError
