.. _unity_page:

===========
Unity Pages
===========

.. note::
  :class:`~psynet.page.UnityPage` functionality is still experimental, and its API is liable to change.

Unity pages are the foundational part for the integration of Unity with PsyNet.
Here are the basic steps necessary for Unity to interact with PsyNet's user interface:

#. Define an experiment timeline using :class:`~psynet.page.UnityPage` elements.
#. Call ``psynet.next_page()``, listen for the JavaScript event ``page_updated``, and respond to the updated data on the page.

Let's look at an example of an experiment consisting of a timeline which includes three :class:`~psynet.page.UnityPage` elements. The first two elements share the same ``session_id`` while the third has a different one. A ``session_id`` corresponds to a Unity session and allows for joining a sequence of :class:`~psynet.page.UnityPage` elements into a single unit.

To accelerate the development process of Unity experiments experiment authors can initialize `UnityPage`'s `debug` instance variable with `True`, see example below. That way instead of starting the WebGL version a debug page is displayed which shows the current state of the experiment, see figure 1. This allows for development without having to recompile each time the WebGL code in Unity editor.

::

  import psynet.experiment
  from psynet.page import (
      InfoPage,
      SuccessfulEndPage,
      UnityPage,
  )
  from psynet.timeline import Timeline

  # Set debug mode during development
  debug = True

  class UnityExperiment(psynet.experiment.Experiment):
      timeline = Timeline(
          UnityPage(
              title="Unity session 1 page 1",
              game_container_width="960px",
              game_container_height="600px",
              contents={"aaa": 111, "bbb": 222,},
              resources="/static",
              time_estimate=5,
              session_id = 1000,
              self.debug = debug,
          ),
          UnityPage(
              title="Unity session 1 page 2",
              game_container_width="960px",
              game_container_height="600px",
              contents={"ccc": 333, "ddd": 444,},
              resources="/static",
              time_estimate=5,
              session_id = 1000,
              self.debug = debug,
          ),
          UnityPage(
              title="Unity session 2 page 1",
              game_container_width="480px",
              game_container_height="300px",
              contents={"eee": 555, "fff": 666,},
              resources="/static",
              time_estimate=5,
              session_id = 2000,
              self.debug = debug,
          ),
          SuccessfulEndPage()
      )

By calling the JavaScript function ``psynet.next_page()`` the user can advance to a follow-up page. ``psynet.next_page()`` takes following arguments:

raw_answer
  The main answer that the page returns.
metadata
  Additional information that might be useful for debugging or other exploration, e.g. time taken on the page.
blobs
  Used for large binaries, e.g. audio recordings.


If the follow-up page has the same ``session_id`` as the preceeding page the JavaScript CustomEvent ``page_updated`` is dispatched. Unity needs to listen for this event and then respond to the updated page information accordingly. The information on the page is accessible through the attributes ``contents`` and ``attributes`` of JavaScript variable ``psynet.page``, where ``contents`` is the main container for holding the experiment specific data. For example, in an experiment about melodies, the ``contents`` property might look something like this: ``{"melody": [1, 5, 2]}``. Here is a JavaScript code snippet demonstrating how to make use of the ``page_updated`` event:

.. code-block:: javascript

  window.addEventListener("page_updated", on_page_updated)

  on_page_updated = function(event) {
      console.log("Event 'page_updated' was dispatched.");
      // Respond to the updated page information accessible through ``psynet.page.contents``.
  };

If the follow-up page has a different ``session_id`` then PsyNet advances to this page by making a standard page request.

On the frontend side ``UnityPage`` is using PsyNet's ``unity-page.html`` template and in debug mode ``unity-debug-page.html``, resp.

For detailed info for how to construct ``UnityPage`` elements please refer to the documentation for :class:`~psynet.page.UnityPage`.
