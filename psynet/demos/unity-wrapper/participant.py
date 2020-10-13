import json

from dallinger.models import Participant
from sqlalchemy import Boolean, String, exc, Float
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

def format_time(time):
    return None if time is None else time.strftime('%Y-%m-%d %H:%M:%S')

def _get_attributes(self):
    if self.property1 is None:
        return {}
    else:
        return json.loads(self.property1)

def _set_attributes(self, attributes):
    self.property1 = json.dumps(attributes)
    return self

def _get(self, key, allow_missing = False):
    assert isinstance(key, str)
    attributes = self.get_attributes()
    try:
        value = attributes[key]
    except KeyError:
        if allow_missing:
            value = None
        else:
            raise
    return value

def _set(self, key, value):
    assert isinstance(key, str)
    attributes = self.get_attributes()
    attributes[key] = value
    self.set_attributes(attributes)
    return self

# Property 2 = have they completed the whole experiment?
@hybrid_property
def complete(self):
    return(bool(int(self.property2)))

@complete.setter
def complete(self, complete):
    self.property2 = int(complete)

@complete.expression
def complete(self):
    return cast(self.property2, Boolean)

def _summarise(self):
    return {
        "id": self.id,
        "complete": self.complete,
        "creation_time": format_time(self.creation_time),
        "end_time": format_time(self.end_time),
        "attributes": self.get_attributes()
    }

# Property 3 = pending bonus
@hybrid_property
def pending_bonus(self):
    if self.property3 is None:
        return 0.0
    else:
        return float(self.property3)

@pending_bonus.setter
def pending_bonus(self, pending_bonus):
    self.property3 = float(pending_bonus)

@pending_bonus.expression
def pending_bonus(self):
    return cast(self.property3, Float)

Participant.get_attributes = _get_attributes
Participant.set_attributes = _set_attributes
Participant.get = _get
Participant.set = _set
Participant.complete = complete
Participant.pending_bonus = pending_bonus
Participant.summarise = _summarise
