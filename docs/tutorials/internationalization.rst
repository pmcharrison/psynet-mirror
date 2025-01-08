====================
Internationalization
====================

Finally, you created an amazing experiment! How cool would it be to run it with participants from all over the world?

Luckily, PsyNet makes it easy to run experiments in different languages. Here's what you need to do:

- mark which strings need to be translated
- perform automatic translation and optionally manually check them

Mark which strings need to be translated
========================================
Let's say you have the following info page in your experiment:


.. code-block:: python

    from markupsafe import Markup
    from psynet.page import InfoPage

    my_info_page = InfoPage(
        Markup(
            f"""
            <h1>Instructions</h1>
            <hr>
            In this experiment, you will listen to different music clips.<br>
            You have to select the music you like most. <br>
            Press "Next" to continue.
            """
        ),
        time_estimate=5
    )

You can easily translate it by marking the strings that need to be translated with the ``_`` function from ``gettext``.


.. code-block:: python

    import os

    from markupsafe import Markup
    from psynet.page import InfoPage
    from psynet.utils import get_translator

    _ = get_translator()

    my_info_page = InfoPage(
        Markup(
            f"""
            <h1>{_("Instructions")}</h1>
            <hr>
            {_("In this experiment, you will listen to different music clips.")} <br>
            {_("You have to select the music you like most.")} <br>
            {_('Press "Next" to continue.')}
            """
        ),
        time_estimate=5
    )


.. note::
    ``get_translator()`` automatically looks for the language specified in your ``config.txt`` file. If you want to use a different language, you can specify it in your config file. For example, if you want to use German, you can set ``language = de`` in your ``config.txt`` file.

.. warning::
    Under the hood PsyNet searches for strings that are marked with ``_``. If you use other functions to mark strings for translation (e.g., ``my_wrapper = get_translator()``), they will not be recognized (e.g., ``my_wrapper("Instructions")``) and not translated. So, make sure to use ``_ = get_translator()``.

Variables
---------
To replace variables in the translation, you have to write the variable in capital letters (underscores are also allowed) and use curly around them.
To resolve the variable, you have to use the ``.format`` method, like here:

.. code-block:: python

    next_button_name = _("Next")
    next_button_text = _('press "{NEXT_BUTTON_NAME}" to continue.').format(NEXT_BUTTON_NAME=next_button_name)

.. warning::
    You have to use the ``.format`` method to replace the variables in the translation. F-strings are not allowed, as it would first replace the variable in the English string and then tries to lookup the translation which would fail. You can read more about translation in the section `Internationalization <../developer/internationalization.html>`_.


Set the correct language
========================
Now you need to tell PsyNet two things:

- The supported languages which are the languages your experiment is translated into, e.g. ``supported_locales = ["de", "en", "nl"]`` if you want to translate to German and Dutch.
- The language you want to use for your experiment, e.g. ``locale = "de"`` if you want to use German.


Perform automatic translation
=============================
Open a terminal in your experiment folder and run the following command:

.. code-block:: console

    psynet translate


This will create a file ``locales/<iso_code>/LC_MESSAGES/experiment.po`` and provide automatic translations for each entry.

PsyNet currently supports two translators:

- OpenAI ChatGPT (``chat_gpt``) and
- Google Translator (``google_translator``)

You can set the default translator in your ``.dallingerconfig`` with the following line:

.. code-block:: text

    [Translator]
    default_translator = <translator_name>

OpenAI ChatGPT
--------------
To use OpenAI ChatGPT, you need to have an OpenAI API key. You can set it in your ``.dallingerconfig`` file with the following line:

.. code-block:: text

    [Translator]
    openai_api_key = <your_openai_api_key>

Google Translator
-----------------
To use Google Translator, you need to do the following steps

- Create a project in the Google Cloud Console
- Enable the Cloud Translation API
- Create a service account
- In the service account and go to the keys tab. Now create a new key as JSON and store it to your computer (home folder is recommended). Now store the path to your ``.dallingerconfig`` file:

.. code-block:: text

    [Translator]
    google_translate_json_path = <path_to_your_json_file>

Manual checking
---------------
You can manually inspect the machine translation by opening the ``locales/<iso_code>/LC_MESSAGES/experiment.po`` file using `POedit editor <https://poedit.net>`__ and check if strings that you marked with ``_`` are translated properly.

Advanced usage
--------------
``_`` assumes the same string is always translated the same way, regardless of the context.
However, sometimes you want to disambiguate the meaning of a string. For example, the word "bank" can mean a financial institution or the side of a river.
To do this you can use ``_p``:

.. code-block:: python

    from psynet.utils import get_translator_with_context

    _p = get_translator_with_context()

    bank_of_river = _p("river", "bank")
    financial_institution = _p("financial", "bank")


.. note::
    However, this use-case is quite rare. In most cases, you can use ``_`` and it will work just fine.


Best practices
--------------
- Use ``_`` for most strings
- Keep the strings short and simple
- Avoid HTML tags in the strings as they might get translated or will lead to word order issues
- Keep the use of inline variables to a minimum, e.g. instead of writing ``_("Make the stimulus as {TARGET} as possible using the slider").format(TARGET=_("happy"))``, write ``_("Adjust the slider to match the target:") + _("happy")``.



To see the translation in action, have a look at the ``translation`` demo.
