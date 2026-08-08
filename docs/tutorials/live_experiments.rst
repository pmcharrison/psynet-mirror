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

    from psynet.websocket import WebSocketMessage, websocket_handler


    class ChooseMessage(WebSocketMessage):
        action: str


    class Exp(psynet.experiment.Experiment):
        @websocket_handler("choose", model=ChooseMessage)
        def choose(self, participant, message: ChooseMessage):
            participant.websocket.send("roundResult", {"text": message.action})

The browser includes the participant and page identity in each WebSocket frame.
The server rejects messages from stale pages, so refreshing the page gives the
participant a fresh connection while old browser tabs stop being able to mutate
the experiment.

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
session is a persisted row linked to the synchronized trials in a group. A
trial-backed :class:`~psynet.session.LiveSessionControl` exposes a
``live_session_config`` object to the browser, including the ``session_id`` and
participant IDs. Browser code passes this config to ``psynet.session.init()``,
then sends a ready event once it has registered its handlers.

Minimal example
---------------

The following example sketches a minimal live rock-paper-scissors round. It is
not a complete experiment, but it shows the moving parts that are specific to a
live interaction.

.. code-block:: python

    from dallinger import db
    from pydantic import Field

    import psynet.experiment
    from psynet.modular_page import ModularPage
    from psynet.page import InfoPage
    from psynet.session import LiveSession, LiveSessionControl
    from psynet.sync import SimpleGrouper
    from psynet.timeline import Timeline
    from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
    from psynet.websocket import WebSocketMessage, websocket_handler


    GROUP_TYPE = "live_rps"
    CHOICES = ["rock", "paper", "scissors"]


    class ChooseMessage(WebSocketMessage):
        session_id: str = Field(min_length=1)
        action: str


    class RockPaperScissorsSession(LiveSession):
        @classmethod
        def build_initial_state(cls, participant_ids, group, trial):
            return {
                "choices": {},
                "finished": False,
            }

        def record_choice(self, participant, action):
            if not self.has_participant(participant):
                return False

            state = dict(self.state or {})
            choices = dict(state.get("choices", {}))
            choices[str(participant.id)] = action
            state["choices"] = choices
            state["finished"] = len(choices) == len(self.participant_ids or [])
            self.state = state
            return True


    class RockPaperScissorsControl(LiveSessionControl):
        external_template = "rps.html"
        macro = "rps_control"

        def build_control_params(self):
            return {"choices": CHOICES}


    class RockPaperScissorsTrial(StaticTrial):
        live_session_class = RockPaperScissorsSession
        time_estimate = 20

        def show_trial(self, experiment, participant):
            return ModularPage(
                "live_rps",
                "Choose rock, paper, or scissors.",
                RockPaperScissorsControl(participant=participant, trial=self),
                save_answer="choice",
                time_estimate=20,
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

        @websocket_handler("choose", model=ChooseMessage)
        def choose(self, participant, message: ChooseMessage):
            live_session = RockPaperScissorsSession.get_current_for_participant(
                participant,
                message.session_id,
                for_update=True,
            )
            if live_session is None:
                return

            if live_session.record_choice(participant, message.action):
                live_session.send_snapshot(self)
                if (live_session.state or {}).get("finished"):
                    live_session.end(self)
                db.session.commit()

And in ``templates/rps.html``:

.. code-block:: html

    {% macro rps_control(config) %}
    <div id="status">Waiting for your partner...</div>

    {% for choice in config.live_session_config.choices %}
        <button type="button" class="choice" data-choice="{{ choice }}" disabled>
            {{ choice }}
        </button>
    {% endfor %}

    <script>
    document.addEventListener("DOMContentLoaded", function () {
        var liveSession = {{ config.live_session_config | tojson }};
        var participantId = String(liveSession.participant_id);
        var submitted = false;

        psynet.session.init(liveSession);

        psynet.session.onSnapshot(function(snapshot) {
            var state = snapshot.state || {};
            var choices = state.choices || {};
            var hasChosen = Object.prototype.hasOwnProperty.call(
                choices,
                participantId
            );

            document.getElementById("status").textContent = hasChosen ?
                "Waiting for your partner..." :
                "Choose your action.";

            Array.prototype.forEach.call(
                document.getElementsByClassName("choice"),
                function(button) {
                    button.disabled = !snapshot.started || hasChosen;
                }
            );
        });

        psynet.session.onEnd(function(snapshot) {
            var choices = snapshot.state.choices || {};
            psynet.nextPage(choices[participantId]);
        });

        psynet.session.ready();

        Array.prototype.forEach.call(
            document.getElementsByClassName("choice"),
            function(button) {
                button.onclick = function () {
                    if (submitted) return;
                    submitted = true;
                    psynet.websocket.send("choose", {
                        action: button.getAttribute("data-choice")
                    });
                    button.disabled = true;
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
