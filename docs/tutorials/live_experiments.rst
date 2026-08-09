Live experiments
================

Many interactive experiments can be implemented with PsyNet's standard
synchronization tools. For example, a two-player rock-paper-scissors experiment
can show each participant a choice page, wait at a
:class:`~psynet.sync.GroupBarrier`, then score the round once both participants
have submitted a response.

This timeline-based approach is straightforward for experiments where participants interact sequentially. 
However, it is not suitable for real-time
interactions that can happen continuously and in no particular order.
Examples include real-time movement on a shared canvas, real-time drawing, or real-time text communication.

WebSockets
----------

PsyNet's native WebSocket API lets browser code send named messages to the
current experiment, and lets the experiment send messages back to one or more
participants.

In the browser:

.. code-block:: javascript

    psynet.websocket.send("choose", {
        action: "rock"
    });

    psynet.websocket.handle("roundResult", function(message) {
        status.textContent = message.text;
    });

In Python:

.. code-block:: python

    from typing import ClassVar

    from psynet.websocket import ClientWebSocketMessage, ServerWebSocketMessage


    class ChooseMessage(ClientWebSocketMessage):
        event_type: ClassVar[str] = "choose"
        action: str

        def handle(self, experiment, participant, receive_time):
            RoundResultMessage(text=self.action).send(participant)


    class RoundResultMessage(ServerWebSocketMessage):
        event_type: ClassVar[str] = "roundResult"
        text: str

The browser includes the participant and page identity in each WebSocket frame.
The server rejects messages from stale pages, so refreshing the page gives the
participant a fresh connection while old browser tabs stop being able to mutate
the experiment. Browser WebSocket handlers are page-scoped; register them from
page scripts so they are recreated for each live page.

Live sessions
-------------

For many live experiments, WebSockets alone are not enough. The experiment also
needs an authoritative shared state that is owned by the server. This state
lets the experiment:

* recover cleanly when a participant refreshes the page;
* ensure that clients render the same session state;
* wait until all participants have loaded the live page;
* reject messages that do not belong to the participant's current live session;
* end the live interaction from the server.

PsyNet provides :class:`~psynet.session.LiveSession` for this purpose. A live
session is a persisted row owned by a synchronized group. It is created
explicitly by a :class:`~psynet.session.LiveSessionInitializer`, which is a
barrier that delegates row creation to the group leader. A
:class:`~psynet.session.LiveSessionControl` resolves that existing row when the
page renders, initializes ``psynet.session`` in the browser, and exposes
``psynet.session.session_id`` and ``psynet.session.participant_id``.
Each concrete live-session subclass defines its own SQL columns for recoverable
public state and can initialize those columns in ``initialize(...)``.
Browser-facing state snapshots are generated automatically from those subclass
columns. Override ``snapshot_state(fields=None, participant=None)`` when you
need to hide columns, rename fields, or include participant-specific recovery
state for the participant requesting a fresh snapshot.
The base ``LiveSession`` class can still be used directly with PsyNet's generic
``var`` store, but explicit subclass columns are preferred for clarity and
performance.
This means you can construct the control in a normal ``ModularPage``
immediately after the initializer in the timeline. Browser code registers its
setup with ``psynet.trial.onEvent("liveSessionInit", ...)``, then sends a ready
event. Once ``LiveSessionControl`` has initialized ``psynet.session``, the
browser automatically attaches the session ID to subsequent
``psynet.websocket.send(...)`` calls from that page.
Register ``psynet.session.onFreshState(...)`` to recover from initial load,
refresh, and reconnect snapshots, and call ``psynet.session.pullState()`` when
the browser needs a fresh copy. ``pullState(["field_a", "field_b"])`` requests
only selected public state fields. For normal gameplay progress and frequent
live updates, prefer custom ``psynet.websocket.send(...)`` messages that include
only the data needed for that update.
When a typed WebSocket message needs the current live-session row, decorate its
``handle`` method with ``@session()``. The decorator resolves the message's
``session_id`` for the current participant and injects the row as a ``session``
argument. All client WebSocket messages include a nullable ``session_id`` field;
``psynet.session`` populates it for messages sent from a live-session control.
Use ``@session(write=True)`` when the handler mutates
session state and should lock the row, commit on success, and roll back on
failure.
Accepted WebSocket messages are saved by default, inbound and outbound. Typed
messages are saved in tables derived from their Pydantic message classes, with
columns for the model fields. If a live update is sent at a high rate, set
``save=False`` on the corresponding message class to skip the default WebSocket
message log.

Private and participant-specific state should still be stored in ordinary SQL
columns; the snapshot override decides what each browser receives. For example:

.. code-block:: python

    from sqlalchemy import Column, Integer

    from psynet.field import PythonDict

    class DemoSession(LiveSession):
        public_score = Column(Integer)
        participant_notes = Column(PythonDict, default=lambda: {})

        def snapshot_state(self, fields=None, participant=None):
            state = super().snapshot_state(fields=None, participant=participant)
            notes = state.pop("participant_notes", {}) or {}
            if participant is not None:
                state["my_note"] = notes.get(str(participant.id))
            if fields is not None:
                state = {field: state[field] for field in fields if field in state}
            return state

``LiveSessionInitializer`` uses a short
``WaitPage(wait_time=0.5, save_answer=False)`` by default while the group waits
for the barrier to release. You can pass a custom ``waiting_logic`` when an
experiment needs a different waiting page.

Minimal example
---------------

The following example sketches a minimal live rock-paper-scissors round. It is
not a complete experiment, but it shows the moving parts that are specific to a
live interaction.

Server-side experiment
~~~~~~~~~~~~~~~~~~~~~~

The Python code defines the persistent session row, typed WebSocket messages,
and timeline. The server owns the authoritative game state and sends custom
events for gameplay progress.

.. code-block:: python

    from typing import ClassVar

    from sqlalchemy import Boolean, Column

    import psynet.experiment
    from psynet.field import PythonDict
    from psynet.modular_page import ModularPage
    from psynet.page import InfoPage
    from psynet.session import LiveSession, LiveSessionControl, LiveSessionInitializer, session
    from psynet.sync import SimpleGrouper
    from psynet.timeline import Timeline, join
    from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
    from psynet.websocket import ClientWebSocketMessage, ServerWebSocketMessage


    GROUP_TYPE = "live_rps"
    CHOICES = ["rock", "paper", "scissors"]


    class ChooseMessage(ClientWebSocketMessage):
        event_type: ClassVar[str] = "choose"
        action: str

        @session(write=True)
        def handle(
            self,
            experiment,
            participant,
            session: "RockPaperScissorsSession",
            receive_time,
        ):
            result = session.record_choice(participant, self.action)
            if result is None:
                return

            finished, choices = result
            if finished:
                for recipient in session.participants:
                    GameFinishedMessage(choice=choices[str(recipient.id)]).send(
                        recipient
                    )


    class GameFinishedMessage(ServerWebSocketMessage):
        event_type: ClassVar[str] = "gameFinished"
        choice: str


    class RockPaperScissorsSession(LiveSession):
        choices = Column(PythonDict, default=lambda: {})
        finished = Column(Boolean, default=False)

        def initialize(self, participant_ids, group):
            self.choices = {}
            self.finished = False

        def record_choice(self, participant, action):
            if not self.has_participant(participant):
                return None

            choices = dict(self.choices or {})
            choices[str(participant.id)] = action
            self.choices = choices
            self.finished = len(choices) == len(self.participant_ids or [])
            return self.finished, choices


    class RockPaperScissorsControl(LiveSessionControl):
        external_template = "rps.html"
        macro = "rps_control"

        def __init__(self, participant):
            self.choices = CHOICES
            super().__init__(
                participant=participant,
                session_class=RockPaperScissorsSession,
                group_type=GROUP_TYPE,
                session_initializer_id="rps_session",
            )


    class RockPaperScissorsTrial(StaticTrial):
        time_estimate = 20

        def show_trial(self, experiment, participant):
            return join(
                LiveSessionInitializer(
                    id_="rps_session",
                    group_type=GROUP_TYPE,
                    session_class=RockPaperScissorsSession,
                ),
                ModularPage(
                    "live_rps",
                    "Choose rock, paper, or scissors.",
                    RockPaperScissorsControl(participant=participant),
                    save_answer="choice",
                    time_estimate=20,
                ),
            )


    class Exp(psynet.experiment.Experiment):
        timeline = Timeline(
            SimpleGrouper(
                group_type=GROUP_TYPE,
                initial_group_size=2,
            ),
            StaticTrialMaker(
                id_="live_rps",
                trial_class=RockPaperScissorsTrial,
                nodes=[StaticNode(definition={})],
                expected_trials_per_participant=1,
                max_trials_per_participant=1,
                sync_group_type=GROUP_TYPE,
            ),
            InfoPage("Finished.", time_estimate=5),
        )

Client-side template
~~~~~~~~~~~~~~~~~~~~

The template waits for ``liveSessionInit``, recovers from fresh state snapshots
after load/reconnect, sends participant choices, and handles the server's custom
``gameFinished`` event.

In ``templates/rps.html``:

.. code-block:: html

    {% macro rps_control(config) %}
    <div id="status">Waiting for your partner...</div>

    {% for choice in config.choices %}
        <button type="button" class="choice" data-choice="{{ choice }}" disabled>
            {{ choice }}
        </button>
    {% endfor %}

    <script>
    psynet.trial.onEvent("liveSessionInit", function () {
        var participantId = String(psynet.session.participant_id);
        var submitted = false;

        function setButtonsEnabled(enabled) {
            Array.prototype.forEach.call(
                document.getElementsByClassName("choice"),
                function(button) { button.disabled = !enabled; }
            );
        }

        function promptForChoice() {
            document.getElementById("status").textContent = "Choose your action.";
            setButtonsEnabled(true);
        }

        psynet.session.onFreshState(function(freshState) {
            // Fresh state is for initial load/reconnect recovery. Normal
            // gameplay progress uses custom events below.
            var state = freshState.state || {};
            var choices = state.choices || {};
            var hasChosen = Object.prototype.hasOwnProperty.call(
                choices,
                participantId
            );
            if (state.finished && hasChosen) {
                psynet.nextPage(choices[participantId]);
                return;
            }

            submitted = hasChosen;
            if (hasChosen) {
                document.getElementById("status").textContent = "Waiting for your partner...";
                setButtonsEnabled(false);
            } else if (freshState.started) {
                promptForChoice();
            }
        });

        psynet.session.onStarted(function() {
            if (!submitted) promptForChoice();
        });

        psynet.websocket.handle("gameFinished", function(message) {
            psynet.nextPage(message.choice);
        });

        psynet.session.ready();

        Array.prototype.forEach.call(
            document.getElementsByClassName("choice"),
            function(button) {
                button.onclick = function () {
                    if (submitted) return;
                    submitted = true;
                    document.getElementById("status").textContent = "Waiting for your partner...";
                    setButtonsEnabled(false);
                    psynet.websocket.send("choose", {
                        action: button.getAttribute("data-choice")
                    });
                };
            }
        );
    });
    </script>
    {% endmacro %}

The complete rock-paper-scissors WebSocket demo in
``demos/experiments/rock_paper_scissors_websocket`` expands this pattern with
multiple rounds, hidden move rows, scoring, and participant-specific reveal
messages. The shared-canvas demo in ``demos/experiments/shared_canvas`` shows a
continuous movement example with low-latency position updates and server-owned
coin collection state.
