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
        "Hi I'm a participant, what's up"
    );

    psynet.websocket.send(
        "shoot",
        {coords: [60, 64], type: "bullet"}
    );

    psynet.websocket.handle("serverMessage", function(message) {
        display.innerHTML = message;
    });

On the Python side, add ``@websocket_handler`` methods to the experiment class:

.. code-block:: python

    import logging

    import psynet.experiment
    from dallinger.experiment import scheduled_task
    from dallinger.models import timenow
    from psynet.participant import Participant
    from psynet.websocket import websocket_handler

    logger = logging.getLogger()


    class Exp(psynet.experiment.Experiment):
        @scheduled_task("interval", seconds=1.0, max_instances=1)
        @staticmethod
        def time_update():
            participants = Participant.query.filter_by(status="working").all()
            for participant in participants:
                participant.websocket.send(
                    "serverMessage",
                    f"Hi, the time is {timenow()}",
                )

        @websocket_handler("userMessage")
        def user_message(self, participant, message):
            logger.info(
                "Participant %i sent the following message: %r",
                participant.id,
                message,
            )

        @websocket_handler("shoot")
        def shoot(self, participant, message):
            coords = message["coords"]
            projectile_type = message["type"]

For structured payloads, pass a Pydantic model to the decorator:

.. code-block:: python

    from pydantic import BaseModel


    class ShootMessage(BaseModel):
        coords: tuple[float, float]
        type: str


    class Exp(psynet.experiment.Experiment):
        @websocket_handler("shoot", model=ShootMessage)
        def shoot(self, participant, message: ShootMessage):
            process_shot(participant, message.coords, message.type)

Recovering shared state after reconnects
----------------------------------------

For multiplayer or other shared real-time pages, store authoritative state in
``psynet.session.LiveSession``. The browser helper ``psynet.session`` requests
fresh snapshots on connect/reconnect and tracks whether all expected participants
are ready:

For custom live controls, subclass ``psynet.session.LiveSessionControl``. The
control derives the browser config (``session_id``, ``group_id``,
``participant_id``, and ``participant_ids``).
Set ``live_session_class`` on the trial class so PsyNet prepares one persisted
live-session row for the synchronized group before the live page is rendered,
then links each participant's trial to that row. This lets server-side
WebSocket handlers update trial state from the authoritative live session.
For now, ``LiveSessionControl`` requires a trial-backed live page.
Experiment code can call ``live_session.end(experiment)`` when its own
completion condition is met; this sends a built-in ``sessionEnd`` event.

.. code-block:: javascript

    psynet.session.init({
        session_id: "round-1"
    });

    psynet.session.onSnapshot(function(snapshot) {
        render(snapshot.state);
    });

    psynet.session.onStarted(function(snapshot) {
        startGameLoop(snapshot.state);
    });

    psynet.session.onEnd(function(snapshot) {
        psynet.nextPage();
    });

    psynet.session.ready();

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
