from requests import *

url = "http://0.0.0.0:5000"

# Advance past the consent form, then try these commands.
# Visit http://0.0.0.0:5000/monitor to see the networks

# Writing a message to the log (default status: info)
post(url + "/log/1", json={
    "message": "Example log message"
})

post(url + "/log/1", json={
    "message": "Example info log message",
    "status": "info"
})

post(url + "/log/1", json={
    "message": "Example warning log message",
    "status": "warning"
})

post(url + "/log/1", json={
    "message": "Example error log message",
    "status": "error"
})

# Setting the participant's bonus (in cents)
post(url + "/set_bonus/1", json={
    "bonus": 5
})

# We begin with 10 ready-created objects.
get(url + "/get_objects/1").content

# We also have one participant
get(url + "/get_participants/1").content
get(url + "/get_participant/1").content

# We can update this participant
post(url + "/update_participant/1", json={
    "attributes": {
        "favourite-color": "red",
        "age": 37
    }
}).content
get(url + "/get_participant/1").content

# We can create a new object
post(url + "/new_object/1", json={
    "attributes": {
        "color": "red",
        "age": 37,
        "pet": "dog"
    }
}).content
get(url + "/get_object/1", json={
    "object_id": 11
}).content

# We can add a state to this object
post(url + "/new_state/1", json={
    "object_id": 11,
    "parent_state_id": 11,
    "attributes": {
        "color": "blue"
    }
}).content

# Now if we try and add a state to the old parent state,
# the state is still created but marked as failed.
post(url + "/new_state/1", json={
    "object_id": 11,
    "parent_state_id": 11,
    "attributes": {
        "color": "purple"
    }
}).content

# We can continue adding states.
post(url + "/new_state/1", json={
    "object_id": 11,
    "parent_state_id": 12,
    "attributes": {
        "color": "orange"
    }
}).content

# We can add responses - these are linked
# to state IDs, not to object IDs.
post(url + "/new_response/1", json={
    "state_id": 14,
    "attributes": {
        "melody-1": [1, 2, 3, 4],
        "melody-2": [4, 3, 2, 1]
    }
}).content

# We can add multiple responses to the same state.
post(url + "/new_response/1", json={
    "state_id": 14,
    "attributes": {
        "melody-1": [1, 1, 1, 1],
        "melody-2": [4, 4, 4, 4]
    }
}).content

# We can also add responses to historic states,
# or even failed states.
post(url + "/new_response/1", json={
    "state_id": 12,
    "attributes": {
        "melody-1": [1, 1, 1, 1],
        "melody-2": [4, 4, 4, 4]
    }
}).content
post(url + "/new_response/1", json={
    "state_id": 13,
    "attributes": {
        "melody-1": [1, 1, 1, 1],
        "melody-2": [4, 4, 4, 4]
    }
}).content

# We can get states using either object IDs or state IDs.
post(url + "/get_state/1", json={
    "state_id": 13
}).content
post(url + "/get_state/1", json={
    "object_id": 11
}).content

# If we set include_responses = True, then responses are also included.
post(url + "/get_state/1", json={
    "state_id": 13,
    "include_responses": True
}).content
post(url + "/get_state/1", json={
    "object_id": 11,
    "include_responses": True
}).content

# We can get responses with get_responses, 
# using either object_id or state_id.
get(url + "/get_responses/1", json={
    "object_id": 11
}).content
get(url + "/get_responses/1", json={
    "state_id": 13
}).content

