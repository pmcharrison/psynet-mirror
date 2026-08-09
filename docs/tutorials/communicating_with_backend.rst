.. |br| raw:: html

   <br />

Communicating with the back-end via custom routes
=================================================

The standard way for PsyNet pages to communicate information to the web server is by submitting an ‘answer’ and proceeding to the next page. This allows the user to take advantage of useful standardized procedures for recording answers within the PsyNet database.

However, for true flexibility, it can be useful to communicate with the server at arbitrary points in time, without necessarily advancing to the next page. To achieve this, we need some custom code on both the Python side (``experiment.py``) and the HTML side (e.g., ``custom-prompt.html``).

Real-time communication with WebSockets
---------------------------------------

For real-time pages, use PsyNet's native WebSocket helpers. On the browser side,
``psynet.websocket.send`` sends a named message to the experiment, and
``psynet.websocket.handle`` registers a callback for messages from the server:

.. code-block:: javascript

    psynet.websocket.send(
        "userMessage",
        {text: "Hi I'm a participant, what's up"}
    );

    psynet.websocket.send(
        "shoot",
        {coords: [60, 64], type: "bullet"}
    );

    psynet.websocket.handle("serverMessage", function(message) {
        display.innerHTML = message.text;
    });

On the Python side, define typed message classes. Browser-to-server messages
subclass ``ClientWebSocketMessage`` and implement ``handle``; server-to-browser
messages subclass ``ServerWebSocketMessage`` and are passed directly to
``participant.websocket.send`` or ``experiment.websocket.send``:

.. code-block:: python

    import logging
    from typing import ClassVar

    import psynet.experiment
    from dallinger.experiment import scheduled_task
    from dallinger.models import timenow
    from psynet.participant import Participant
    from psynet.websocket import ClientWebSocketMessage, ServerWebSocketMessage

    logger = logging.getLogger()


    class ServerMessage(ServerWebSocketMessage):
        event_type: ClassVar[str] = "serverMessage"
        text: str


    class UserMessage(ClientWebSocketMessage):
        event_type: ClassVar[str] = "userMessage"
        text: str

        def handle(self, experiment, participant, receive_time):
            logger.info(
                "Participant %i sent the following message: %r",
                participant.id,
                self.text,
            )


    class ShootMessage(ClientWebSocketMessage):
        event_type: ClassVar[str] = "shoot"
        coords: tuple[float, float]
        projectile_type: str

        def handle(self, experiment, participant, receive_time):
            process_shot(participant, self.coords, self.projectile_type)


    class Exp(psynet.experiment.Experiment):
        @scheduled_task("interval", seconds=1.0, max_instances=1)
        @staticmethod
        def time_update():
            participants = Participant.query.filter_by(status="working").all()
            for participant in participants:
                participant.websocket.send(
                    ServerMessage(text=f"Hi, the time is {timenow()}"),
                )

By default, PsyNet saves each accepted WebSocket message, inbound and outbound.
Messages are saved only after the server has matched the inbound message class,
checked that the message comes from the participant's current page, and applied
Pydantic validation. Messages are saved in a table derived from the message
class, with columns for the model fields. For example, ``PositionMessage`` is
saved in ``position_message`` with its own ``session_id``, ``x``, ``y``, and
related columns. For very high-frequency messages, set ``save=False`` on the
message class:

.. code-block:: python

    class PositionMessage(ClientWebSocketMessage):
        event_type: ClassVar[str] = "position"
        save: ClassVar[bool] = False

        x: float
        y: float

        def handle(self, experiment, participant, receive_time):
            broadcast_position_update(participant, self)

Recovering shared state after reconnects
----------------------------------------

For multiplayer or other shared real-time pages, WebSockets are typically
combined with :class:`psynet.session.LiveSession`, which stores the server's
authoritative state and helps clients recover after refreshes. See
:doc:`live_experiments` for a full explanation and a minimal live
rock-paper-scissors example.

Custom HTTP routes
------------------

The Python side involves using a special decorator called ``experiment_route``. We use this in our ``Experiment`` class. For example, we might write something like this:

.. code-block:: python

    import psynet.experiment
    from dallinger.experiment import experiment_route
    from datetime import datetime

    class Exp(psynet.experiment.Experiment):
        @experiment_route("/current_date_and_time", methods=["GET"])
        @classmethod
        def current_date_and_time(cls):
            now = datetime.now()
            date = now.strftime("%d/%m/%Y")
            time = strftime("%H:%M:%S")
            return {
                "date": date,
                "time": time,
            }

This code defines a custom *HTTP route* that returns the current date and time. If we spin up our experiment in debug mode, we can access this route in the web browse by navigating to the following address: http://localhost:5000/current_date_and_time.

.. note::
    Valid responses from the ``experiment_route`` function are strings, tuples, or dictionaries.

.. note::
    Custom experiment routes must currently be defined as class methods (see the use of the ``classmethod`` decorator in the example. A limitation of this is that it is slightly awkward to access ``Experiment`` variables; you can’t just write ``cls.var``. Instead, you currently must write something like this:

.. code-block:: python

    @experiment_route("/random", methods=["GET"])
    @classmethod
    def random_route(self):
       import random
       from dallinger import db

       exp = self.new(db.session)

       x = random.randint(1, 100)
       exp.var.random = x
       db.session.commit()

       return {"value": x}

See how we instantiate an ``Experiment`` object, connecting it to a database session, before we can access ``Experiment`` variables. Note also how we call ``db.session.commit()`` to ensure that the changes are persisted to the database.

If we want to access this data in Javascript, we can write code like the following:

.. code-block:: python

    dallinger.get("/current_date_and_time").done((resp) => {
        // Do something with the response, e.g. print it
        console.log(resp)
    })

What is the ``.done()`` doing here? We need this because making HTTP queries happens *asynchronously* in Javascript. This means that we can’t access the result straightaway; we need instead to wait for it. We write the ``.done()`` expression, with its anonymous function, to define what should happen once the route returns.

In some cases, we might want our HTTP route to take some input data. There are several ways of achieving this, depending on how complex we expect our input data to be.

The simplest approach involves passing the data as part of the HTTP route’s URL. For example, we might define an ``add`` function that is accessed via a URL like the following: `http://localhost:5000/add?x=5&y=3`

Here ``x=5`` and ``y=3`` are called *URL parameters*. We can access URL parameters in our PsyNet route by writing code like ``request.values["x"]``.

**Important:** All URL parameters are interpreted as strings by default. If you want to interpret them as numbers, then you must convert them accordingly.
For example, suppose we want to define an HTTP route that adds two numbers. We would write it like this:

.. code-block:: python

    from flask import request
    import psynet.experiment
    from dallinger.experiment import experiment_route

    class Exp(psynet.experiment.Experiment):
        @experiment_route("/add", methods=["GET"])
        @classmethod
        def add(cls):
            x = request.values["x"]
            y = request.values["y"]
            return {
                "result": x + y
            }

We could then access this route from Javascript as follows:

.. code-block:: python

    dallinger.get("/add", {x: x, y: y}).done((resp) => {
        // Do something with the response, e.g. print it
        console.log(resp.result)
    })

We wrote ``methods=["GET"]`` in the above, which labels the route as a GET route. We access GET routes by writing ``dallinger.get()``, as above. By convention, GET routes do *not* edit the state of the server; they are used for getting information, not for saving it. If we want to save information on the server, we would instead define our route as a POST route, writing ``methods=["POST"]``, and using ``dallinger.post()`` to access the route from Javascript.

If you are writing a POST route in PsyNet, you are likely saving some kind of information via SQLAlchemy. This is a situation where you will need to add the following lines, to make sure that your data is committed properly!

Here’s an example of setting a participant variable via a custom route:

.. code-block:: python

    from flask import request
    import psynet.experiment
    from dallinger.experiment import experiment_route
    from dallinger import db
    from dallinger.experiment_server.utils import success_response

    class Exp(psynet.experiment.Experiment):
        @experiment_route("/add", methods=["POST"])
        @classmethod
        def set_dollars(cls):
            participant_id = int(request.values["participant_id"])
            dollars = float(request.values["dollars"])
            p = Participant.query.filter_by(id=participant_id).one()
            p.var.dollars = dollars
            db.session.commit()
            return success_response()

.. note::
    If the HTTP request isn’t meant to return any data, it’s conventional to return a ``success_response``, as demonstrated above. This can be imported from ``dallinger.experiment_server.utils``.

It is also possible to send more complex objects to PsyNet’s backend, including arbitrarily nested dictionaries/lists, and even blobs corresponding to raw media files. For a reference on how to do this, see the ``submitGenericResponse`` function in PsyNet’s ``timeline-page.html`` file (which describes the relevant front-end) and the ``route_response`` function in ``experiment.py`` (which describes the relevant back-end).
