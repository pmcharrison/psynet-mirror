import random
import json

from sqlalchemy import Boolean, String, Integer
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

from dallinger.networks import Chain
from dallinger.models import Info, Transformation, Node
from dallinger.nodes import Source, Agent

from operator import attrgetter

from typing import Optional

import rpdb

def format_time(time):
    return None if time is None else time.strftime('%Y-%m-%d %H:%M:%S')
    
class Response(Info):
    __mapper_args__ = {"polymorphic_identity": "response"}

    def __init__(self, state, attributes, participant_id):
        contents = json.dumps(attributes)

        #### This section is modified from Dallinger core.
        # We comment out the fail check, because we want to be able to create
        # responses to failed states.

        # if origin.failed:
        #     raise ValueError("{} cannot create an info as it has failed".format(origin))

        self.origin = state
        self.origin_id = state.id
        self.contents = contents
        self.network_id = state.network_id
        self.network = state.network

        #### end Dallinger core section

        self.participant_id = participant_id

    def get_attributes(self):
        return json.loads(self.contents)

    def state(self):
        return self.origin

    def object(self):
        return self.state().object()

    def summarise(self):
        return {
            "response_id": self.id,
            "creation_time": format_time(self.creation_time),
            "object_id": self.object().id,
            "state_id": self.state().id,
            "attributes_id": self.get_attributes()
        }

    @hybrid_property
    def participant_id(self):
        if self.property1 is None:
            return None
        else:
            return int(self.property1)

    @participant_id.setter
    def participant_id(self, participant_id: int):
        self.property1 = repr(participant_id)

    @participant_id.expression
    def participant_id(self):
        return cast(self.property1, Integer) 

class Object(Chain):
    __mapper_args__ = {"polymorphic_identity": "object"}

    @hybrid_property
    def current_state_id(self):
        if self.property1 is None:
            return None 
        else:
            return int(self.property1)

    @current_state_id.setter
    def current_state_id(self, current_state_id: int):
        self.property1 = repr(current_state_id)

    @current_state_id.expression
    def current_state_id(self):
        return cast(self.current_state_id, Integer) 

    def __init__(self, exp, attributes):
        super().__init__()
        self.max_size = 1e7
        self.role = "experiment"
        self.new_state(
            exp,
            attributes, 
            parent_state_id=None,
            clear_attributes=False
        )

    def get_current_state(self):
        if self.current_state_id is None:
            return None
        else:
            return State.query.filter_by(id=self.current_state_id).one()

    def get_responses(self):
        return self.get_current_state().get_responses()

    def get_attributes(self):
        state = self.get_current_state()
        return dict() if state is None else state.get_attributes()

    def all_states(self, include_failed: bool):
        arg = "all" if include_failed else False
        return self.nodes(failed=arg)

    def summarise(self, include_responses: bool, include_failed: bool):
        states = self.all_states(include_failed=include_failed)
        states.sort(key=attrgetter("creation_time"))
        state_summaries = [s.summarise(include_responses = include_responses) for s in states]

        return {
            "object_id": self.id,
            "creation_time": format_time(self.creation_time),
            "states": state_summaries
        }

    def new_state(self, exp, attributes, parent_state_id: Optional[int], clear_attributes: bool, participant=None):        
        new_attributes = attributes if clear_attributes else {**self.get_attributes(), **attributes}
        
        new_state = State(new_attributes, object = self, participant=participant)
        exp.session.add(new_state)
        exp.session.commit()
        
        if parent_state_id is None:
            if self.current_state_id is not None:
                raise ValueError("Failed to provide a parent_state_id when one was required.")
            self.current_state_id = new_state.id
        else:
            parent_state = State.query.filter_by(id=parent_state_id).one()
            parent_state.connect(new_state)
            if parent_state_id == self.current_state_id:
                self.current_state_id = new_state.id
            else:
                new_state.fail()

        exp.session.commit()

        return new_state

    # def new_response(self, attributes, participant_id):
    #     state = self.get_current_state()
    #     assert state is not None
    #     return state.new_response(attributes, participant_id)


class State(Node):
    __mapper_args__ = {"polymorphic_identity": "state"}

    def __init__(self, attributes, object, participant):
        super().__init__(network=object, participant=participant)
        self.set_attributes(attributes)

    def object(self):
        return self.network

    # def connect_to_parent(self):
    #     previous_states = [
    #         s for s in self.object().all_states()
    #         if s.id != self.id 
    #         and s.creation_time < self.creation_time
    #     ]
    #     if previous_states:
    #         parent = max(previous_states, key=attrgetter("creation_time"))
    #         parent.connect(whom=self)

    def new_response(self, attributes, participant_id):
        return Response(self, attributes, participant_id)

    def get_responses(self):
        responses = self.infos(failed="all") 
        responses.sort(key=attrgetter("creation_time"))
        return responses

    def summarise(self, include_responses: bool):
        res = {
            "state_id": self.id,
            "object": self.object().id,
            "creation_time": format_time(self.creation_time),
            "attributes": self.get_attributes()
        }
        if include_responses:
            res["infos"] = [info.summarise() for info in self.infos(failed="all")]
        return res

    def get_attributes(self):
        if self.property1 is None:
            return {}
        else:
            return json.loads(self.property1)

    def set_attributes(self, attributes: dict):
        self.property1 = json.dumps(attributes)
        return self

    def get_attribute(self, key: str, allow_missing = False):
        vars = self.get_attributes()
        try:
            value = vars[key]
        except KeyError:
            if allow_missing:
                value = None
            else:
                raise
        return value

    def set_attribute(self, key: str, value):
        attrs = self.get_attributes()
        attrs[key] = value
        self.set_attributes(attrs)
        return self
