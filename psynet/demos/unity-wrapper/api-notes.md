# Dallinger-Unity API

These are all HTTP requests that are made to the
Dallinger web app. They all take a common form: a URL composed of the command
followed by the participant ID, accompanied by a JSON object specifying request
arguments as key-value pairs. The participant ID is there in case we want to
limit the privileges of given participants.

See `api-examples.py` for example usage.

## Log API

### POST: /log/<participant_id>

- Arguments: A JSON object with one compulsory field, `message`, providing the
  message to be written to the log,
  and one optional field, `status`, which can be either `"info"` (default), `"warning"`,
  or `"error"`.

## Participant API

### POST: /set_bonus/<participant_id>

- Arguments: A JSON object with one field, `bonus`, identifying the
  new value of the participant's bonus (in cents).

### POST: /get_participants/<participant_id>

- Arguments: None. 
- Returns: A JSON object enumerating all the participants in the study and their
  properties.

### POST: /get_participant/<participant_id>

- Arguments: None. 
- Returns: A JSON object enumerating the current participant's properties. 

### POST: /update_participant/<participant_id>

- Arguments: A JSON object with one field, `attributes`, corresponding to a list
  of key-value pairs defining how fields in the current participant should be
  overwritten.
- Returns: A message confirming the action undertaken, e.g. "Updated 3 attribute(s)."

## Object API

### POST: /get_objects/<participant_id>

- Returns: a JSON object enumerating all objects in the study and their properties.
- Expects a JSON object containing the following fields:
  a) `include_responses` (optional, Boolean, defaults to `False`),
  determines whether to include the responses associated with object states,
  b) `include_failed` (optional, Boolean, defaults to `False`),
  determines whether to include failed states.

### POST: /new_object/<participant_id>

- Arguments: A JSON object with one field, `attributes`, corresponding to a list
  of key-value pairs defining the attributes of the object to be created.
- Returns: A JSON object with one field, `object_id`, corresponding to the ID of
  the created object.

### POST: /get_object/<participant_id>

- Returns: A JSON describing the attributes of the object identified by
  `object_id`, as well as all of its states (historic and present), ordered from
  oldest to newest.
- Expects a JSON object containing the arguments
  a) `object_id`, which identifies the relevant object,
  b) `include_responses` (optional, Boolean, defaults to `False`),
  determines whether to include the responses associated with object states,
  c) `include_failed` (optional, Boolean, defaults to `False`),
  determines whether to include failed states.
 
### POST: /new_state/<participant_id>

This function creates a new state for a given object, altering various object
attributes in the process. Responses are not carried over from the previous
state. Even if the `parent_state_id` no longer corresponds to the object's current state,
then the state is still registered but marked as failed.

- Expects a JSON with the arguments
  a) `attributes` (key-value pairs for fields to set), 
  b) `object_id` (integer),
  c) `parent_state_id` (integer, identifies the parent state),
  d) `clear_attributes` (Boolean, defaults to `False`), which determines
  whether or not to clear all existing attributes before setting new ones.
- Returns: A JSON object with one field, `state_id`, corresponding to the ID of
  the created state.

### POST: /get_state/<participant_id>

- Expects a JSON object containing the arguments
  a) EITHER `object_id`, which identifies the relevant object,
  OR `state_id`, which identifies the relevant state;
  b) `include_responses` (optional, Boolean, defaults to `False`).
- Returns: 
  If `object_id` is provided, the output constitutes a JSON
  characterising the current state of the object identified by `object_id`.
  If `state_id` is provided, the output instead characterises
  the object state identified by `state_id`.
  If `include_responses` is `True`, then the output will include
  the responses associated with the state.
  An error is thrown if both `object_id` and `state_id` are provided.
  
### POST: /get_responses/<participant_id>

- Expects a JSON object containing 
- EITHER `object_id`, which identifies the relevant object,
  OR `state_id`, which identifies the relevant state.
- Returns:
  If `object_id` is provided, the output constitutes a JSON list of
  responses to the current state of the object identified by `object_id`.
  If `state_id` is provided, the output lists the responses to
  the object state identified by `state_id`.

### POST: /new_response/<participant_id>

- Expects a JSON with the arguments
  a) `state_id` (integer, identifies the object state with which the response
  should be associated),
  b) `attributes` (a list of key-value pairs defining the attributes
  of the response to be created).
- Returns: A JSON object with one field, `response_id`, corresponding to the ID of
  the created state.
  