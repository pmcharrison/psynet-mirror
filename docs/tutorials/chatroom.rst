.. _Chatroom:

=========
Chatrooms
=========

PsyNet provides a chatroom component that lets participants send real-time text
messages to each other during an experiment. It is designed to be embedded
inside a :class:`~psynet.modular_page.ModularPage` and communicates over a
WebSocket channel.

Overview
--------

There are two pieces you need to wire together:

* :class:`~psynet.chatroom.EnableChatrooms` — a timeline element that opens
  the server-side WebSocket handler.  Place it **once** near the top of your
  experiment timeline, before any page that uses a chatroom.

* :class:`~psynet.chatroom.ChatRoom` — the per-page component that configures
  the chatroom UI for a specific room.  Pass it as the ``chatroom`` keyword
  argument to a :class:`~psynet.modular_page.ModularPage`.

Basic setup
-----------

1. Add :class:`~psynet.chatroom.EnableChatrooms` to your timeline::

    from psynet.chatroom import ChatRoom, EnableChatrooms
    from psynet.timeline import Timeline

    class MyExperiment(Experiment):
        timeline = Timeline(
            EnableChatrooms(),
            ...
        )

2. Pass a :class:`~psynet.chatroom.ChatRoom` instance to the ``chatroom``
   parameter of :class:`~psynet.modular_page.ModularPage`::

    from psynet.modular_page import ModularPage, NullControl

    ModularPage(
        "chat",
        "Chat with your partner.",
        NullControl(),
        chatroom=ChatRoom(room_id="my_room"),
        time_estimate=60,
    )

   The ``room_id`` string determines which participants share the same chat
   history and occupancy list.  Participants whose ``room_id`` values match
   will see each other's messages.

Room IDs
--------

The ``room_id`` can be any string.  Experiments may want separate groups with
private rooms. In such cases you can use an ID derived from a group
identifier::

    chatroom=ChatRoom(
        room_id=f"group_{participant.sync_group.id}",
        show_participants=True,
        show_history=True,
    )

Options
-------

:class:`~psynet.chatroom.ChatRoom` accepts two optional boolean flags:

``show_participants``
    Display a sidebar listing the participant IDs currently in the room.
    Defaults to ``False``.

``show_history``
    Deliver all prior messages for this room to a participant when they first
    join.  Useful when a participant might reconnect mid-session or when
    a group needs shared context from an earlier page.
    Defaults to ``False``.

Message storage
---------------

Every message sent through a chatroom is persisted in the
:class:`~psynet.chatroom.ChatMessage` database table, which records the
sender's participant and node IDs, the room ID, the message content, and the
server-side receive time.  This data is available in the exported dataset after
the experiment completes.

Participant variables
---------------------

:class:`~psynet.chatroom.EnableChatrooms` tracks room membership by writing
two keys into the :class:`~psynet.participant.Participant` ``details`` JSONB field:

``chatroom_subscribed`` *(bool)*
    ``True`` while the participant is actively joined to a room; set to
    ``False`` when they send a ``leave_room`` message (e.g. on page exit).

``chatroom_room_id`` *(str)*
    The ``room_id`` the participant is currently subscribed to.

These values are used internally to build the occupancy list broadcast to
all room members, and can be queried efficiently at the database level.
You can read them in experiment code if you need to react to a participant's
current room membership, for example::

    if participant.details.get("chatroom_subscribed", False):
        current_room = participant.details["chatroom_room_id"]

Customising the chatroom
------------------------

The built-in chatroom widget is implemented in
``psynet/templates/macros/chatroom.html`` as a Jinja macro named
``chatroom_widget``.  To replace it with your own HTML/CSS/JS, subclass
:class:`~psynet.chatroom.ChatRoom` and point it at a custom template file
stored in your experiment's ``templates/`` directory:

.. code-block:: python

    class MyChatRoom(ChatRoom):
        macro = "my_chatroom"
        external_template = "my-chatroom.html"

Then create ``templates/my-chatroom.html`` in your experiment directory.
The macro receives the ``ChatRoom`` instance as its sole ``config`` argument,
so every attribute you set on the subclass is accessible inside the template:

.. code-block:: html

    {% macro my_chatroom(config) %}
    {# config.room_id, config.show_participants, config.show_history
       and any custom attributes you add are all available here. #}
    <div id="chatroom-widget">
        ...
    </div>
    <script>
        var ROOM_ID = {{ config.room_id | tojson }};
        var CHANNEL = {{ config.channel | tojson }};
        var SHOW_PARTS   = {{ "true" if show_participants else "false" }};
        var SHOW_HISTORY = {{ "true" if show_history else "false" }};
        var MY_ID        = String(dallinger.identity.participantId);
        ...
    </script>
    {% endmacro %}

If you only need minor CSS changes (e.g. a different height or colour scheme)
you can override the built-in IDs (``#chatroom-widget``,
``#chatroom-messages``, ``#chatroom-input-row``, etc.) in your experiment's
custom stylesheet instead of replacing the template entirely.

Demo
----

The rock-paper-scissors demo illustrates a chatroom that opens after each trial
round, allowing the two players to discuss the outcome before continuing:

.. literalinclude:: ../../demos/experiments/rock_paper_scissors/experiment.py
   :language: python
