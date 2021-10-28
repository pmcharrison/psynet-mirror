# Unity integration - Interface description

## Basic example

There exist two main ways for Unity to interact with PsyNet's user interface:

1. Defining an experiment timeline using ``UnityPage`` elements
2. Calling ``psynet.nextPage()`` and then listening to the JavaScript event ``pageUpdated``

Let's look at an example of an experiment consisting of an experiment timeline which includes three ``UnityPage`` elements. The first two elements share the same ``session_id`` while the third has a different one. A ``session_id`` corresponds to a Unity session and allows for joining a sequence of ``UnityPage`` elements into a single unit.

```python
from uuid import uuid4

import psynet.experiment
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    UnityPage,
)
from psynet.timeline import Timeline


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class UnityExperiment(psynet.experiment.Experiment):
    session_id = str(uuid4())
    timeline = Timeline(
        UnityPage(
            title="Unity session 1 page 1",
            game_container_width="960px",
            game_container_height="600px",
            contents={"aaa": 111, "bbb": 222,},
            resources="/static",
            time_estimate=5,
            session_id = session_id,
        ),
        UnityPage(
            title="Unity session 1 page 2",
            game_container_width="960px",
            game_container_height="600px",
            contents={"ccc": 333, "ddd": 444,},
            resources="/static",
            time_estimate=5,
            session_id = session_id,
        ),
        UnityPage(
            title="Unity session 2 page 1",
            game_container_width="480px",
            game_container_height="300px",
            contents={"eee": 555, "fff": 666,},
            resources="/static",
            time_estimate=5,
            session_id = str(uuid4()),
        ),
        SuccessfulEndPage()
    )
```

By calling the JavaScript function ``psynet.nextPage()`` the user can advance to a follow-up page. If this page has the same ``session_id`` as the preceeding page the JavaScript CustomEvent ``pageUpdated`` is dispatched. Unity needs to listen for this event and then respond to the updated page information accordingly. This information is accessible through attributes ``contents`` and ``attributes`` of JavaScript variable ``psynet.page``, where ``contents`` is the main container to hold the experiment specific data. For example, in an experiment about melodies, the ``contents`` property might look something like this: ```
python {"melody": [1, 5, 2]}```. Here is a JavaScript code snippet demonstrating how to make use of the ``pageUpdated`` event.

```javascript
window.addEventListener("pageUpdated", onPageUpdated)

onPageUpdated = function(event) {
    console.log("Event 'pageUpdated' was dispatched.");
    // Respond to the updated page information accessible
    // through ``psynet.page.contents``
};

```

If the follow-up page has a different ``session_id`` then PsyNet advances to this page by making a standard page request. 

For how to construct ``UnityPage`` elements please refer to the documentation for the ``UnityPage`` class, for convenience also included below.

## UnityPage class

```python
class UnityPage(Page):
    """
    This is the main page when conducting Unity experiments. Its attributes ``contents`` and ``attributes`` can be accessed through the JavaScript variable ``psynet.page`` inside the page template.

    Ín order to conclude this page call the ``psynet.nextPage`` function which has following parameters:

    * ``raw_answer``: The main answer that the page returns.

    * ``metadata``: Additional information that might be useful for debugging or other exploration, e.g. time taken on the page.

    * ``blobs``: Use this for large binaries, e.g. audio recordings.

    Once the ``psynet.nextPage`` function is called, PsyNet will navigate to a new page if the new page has a different session_id compared to the current page, otherwise it will update the page while preserving the ongoing Unity session, specifically updating ``psynet.page`` and triggering the JavaScript event ``pageUpdated`` in the ``window`` object.

    Parameters
    ----------

    title:
        The title of the experiment to be rendered in the HTML title-tag of the page.

    game_container_width:
        The width of the game container, e.g. '960px'.

    game_container_height:
        The height of the game container, e.g. '600px'.

    resources:
        The path to the directory containing the Unity files residing inside the "static" directory. The path should start with "/static" and should comply with following basic structure:

        static/
        ├── css/
        └── scripts/

        css: Contains stylesheets

        scripts: Contains JavaScript files

    contents:
        A dictionary containing experiment specific data.

    time_estimate:
        Time estimated for the page.

    session_id:
        If session_id is not None, then it must be a string. If two consecutive pages occur with the same session_id, then when it’s time to move to the second page, the browser will not navigate to a new page, but will instead update the JavaScript variable psynet.page with metadata for the new page, and will trigger an event called pageUpdated. This event can be listened for with JavaScript code like window.addEventListener(”pageUpdated”, ...).

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """
```
