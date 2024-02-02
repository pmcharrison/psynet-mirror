.. |br| raw:: html

   <br />

Writing custom frontends
=========================

PsyNet provides a library of built-in user interface components, including text boxes, audio recorders, video players, vector animations, and so on. It is possible to design many experiments using these built-in components, but for true flexibility, one needs the ability to program one’s own front-end components from scratch.

The recommended way to do this is by creating custom modular page components. As a reminder, modular pages combine together two types of elements: a *prompt*, which displays some kind of stimulus to the user, and a *control*, which gives the user some mechanism for responding to the prompt.

The built-in ‘``modular_page``’ demo demonstrates how one can write custom prompts and controls in PsyNet.

.. note::
    The below documentation refers to a slightly updated form of this demo that (at the time of writing) has not yet been merged to PsyNet’s master branch.

Custom prompts
--------------

Let’s see first how the user defines a custom prompt. Looking at ``experiment.py``, we see the following Python code:

.. code-block:: python

    class HelloPrompt(Prompt):
        macro = "with_hello"
        external_template = "custom-prompts.html"

        def __init__(
                self,
                username: str,
                text: Union[None, str, Markup] = None,
                text_align: str = "left",
        ):
            super().__init__(text=text, text_align=text_align)
            self.username = username

There are three important components here.

First, we tell PsyNet that our ``HelloPrompt`` prompt is going to be associated with a macro called ‘``with_hello``’.

Second, we tell PsyNet that this macro is going to be defined in an external template, and that external template is going to be called ``custom-prompts.html``. External templates are stored in a folder called ``templates`` located in the experiment directory; we’ll have a look at ``templates/custom-prompts.html`` in just a moment.

Third, we write a custom constructor function. This function inherits from the superclass ``Prompt``, but adds an extra argument, ``username``, which is saved as an instance attribute (``self.username = username``).

Let’s have a look at ``templates/custom-prompts.html``.

.. code-block:: html

    {% macro with_hello(config) %}
       <h1>Hello, {{ config.username }}!</h1>

       {{ psynet_prompts.simple(config) }}

    {% endmacro %}

The curly braces and percent sign notation comes from `Jinja <https://jinja.palletsprojects.com/en/3.0.x/>`_. Jinja is a templating language used for programmatically generating HTML. An important feature of Jinja is the use of *macros*, which are functions responsible for generating code. Everything else is HTML code.

Here we are defining a macro called ``with_hello``. This macro follows a standard form for all PsyNet prompt/control macros. In particular, it takes a single argument, ‘``config``’, which is used to bring configuration information from Python into Jinja. Note that this variable ‘``config``’ has nothing to do with config.txt, it is simply a way for psynet to transfer information to Jinja as we will explain below. We can access information from this config object by writing expressions of the following form:

.. code-block:: html

    {{ config.username }}

The double brackets is special Jinja syntax that means ‘evaluate the contents of these brackets as a Python expression’. The config object is a Python object, and we can access its attributes (for example ``username``) just like normal Python object attributes, using ‘.’ notation.

When Jinja evaluates an expression surrounded with double brackets, it takes the results and writes it into the HTML file. So, suppose ``config.username`` was equal to ‘Jeff’, then the following Jinja passage

.. code-block:: html

    <h1>Hello, {{ config.username }}!</h1>

would evaluate to the following HTML passage:

.. code-block:: html

    <h1>Hello, Jeff!</h1>

So what exactly *is* the ``config`` object? It corresponds directly to the ``Prompt`` or ``Control`` object that has been inserted into the modular page. Any attributes (or indeed methods) of these objects are directly accessible within the Jinja macro. Look again at the definition of ``HelloPrompt``:

.. code-block:: python

    class HelloPrompt(Prompt):
        macro = "with_hello"
        external_template = "custom-prompts.html"

        def __init__(
                self,
                username: str,
                text: Union[None, str, Markup] = None,
                text_align: str = "left",
        ):
            super().__init__(text=text, text_align=text_align)
            self.username = username

See how the ``username`` attribute was set within the ``__init__`` function, making it an instance attribute, i.e. an attribute that varies between ``HelloPrompt`` instances.

We can also define prompts with *class attributes*; these attributes are fixed for all instances of a given class. In the below example, ``background_color`` is a class attribute:

.. code-block:: python

    class HelloPrompt(Prompt):
        macro = "with_hello"
        external_template = "custom-prompts.html"
        background_color = "red"

As before, we can access them using Jinja curly brackets:

.. code-block:: html

    <h1 style="background-color: {{ config.background_color }}">
        Hello, {{ config.username }}!
    </h1>

We can even access methods within Jinja:

.. code-block:: python

    class HelloPrompt(Prompt):
        macro = "with_hello"
        external_template = "custom-prompts.html"

        def get_message(self):
            return f"Today's date is { self.print_date() }"

Accessed in Jinja as follows:

.. code-block:: html

    <p> {{ config.get_message() }} </p>

Let’s look once more at the definition of the ``with_hello`` macro:

.. code-block:: html

    {% macro with_hello(config) %}
       <h1>Hello, {{ config.username }}!</h1>

       {{ psynet_prompts.simple(config) }}

    {% endmacro %}

We have already talked about the first part, which pulls information from ``config.username``. The second part calls a macro called ‘``simple``’ from PsyNet’s built-in library of prompts. The source code for PsyNet’s prompt library can be seen in ``psynet/templates/macros/prompt.html``. It is possible to reuse any of these macros when writing your own prompt. The ``simple`` macro simply displays some text to the participant, which is what we use here.

Custom controls
---------------

Custom controls are defined in a similar way. Looking in the same demo, we have the following definition for ``ColorText``:

.. code-block:: python

    class ColorText(Control):
        macro = "color_text_area"
        external_template = "custom-controls.html"

        def __init__(self, color):
            super().__init__()
            self.color = color

        @property
        def metadata(self):
            return {"color": self.color}

As before, the class has ``macro`` and ``external_template`` attributes, which tell PsyNet where to find the class’s Jinja macro. It additionally has a ``color`` instance attribute, which is set in the instance’s constructor function (``__init__()``). Lastly, it has a ``metadata`` method, which generates metadata that will be saved along with the participant’s response. This method is optional; if you implement it, it should provide some non-essential additional information about the participant’s response.

This ``ColorText`` definition is complemented by the following macro definition in ``custom-controls.html``:

.. code-block:: html

    {% macro color_text_area(config) %}

        <textarea id="text-input" type="text" class="form-control" style="background-color: {{ config.color }}; margin-bottom: 40px;"></textarea>

        <script>
            psynet.stageResponse = function() {
                psynet.response.staged.rawAnswer = document.getElementById('text-input').value
            }
        </script>

    {% endmacro %}

This macro has several important components.

* First, there is a ``textarea`` element, a standard HTML element corresponding to a text box that can be filled in by the user. This textbox has a customizable background color determined by the value of ``config.color``.

* Second, a function is defined called ``psynet.stageResponse``. This function is written in Javascript,
  and extracts the current contents of the textbox as a string (e.g., ‘Hello’).
  It then saves this string to ``psynet.response.staged.rawAnswer``.
  This 'stages' the answer, so that when the page is exited (by clicking the 'Next' button) this answer
  is submitted to the PsyNet back-end.

In some cases we might want to postprocess this response in Python before we save it. This can be achieved by writing a custom ``format_answer`` method for the custom ``Control`` class. For example, if we wanted to capitalize all the responses, we could write something like this:

.. code-block:: python

    def format_answer(self, raw_answer, **kwargs):
        return raw_answer.capitalize()

The ``raw_answer`` argument here corresponds to the data that was saved in ``psynet.stageResponse``. In this example, this data will be a string, corresponding to the contents of the textbox; however, more complex forms of data are supported, for example lists and dictionaries.
