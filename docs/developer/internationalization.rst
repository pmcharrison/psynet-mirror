.. _developer:
.. highlight:: shell

====================
Internationalization
====================

The internationalization pipeline can be difficult to understand at first. This document aims to explain the process behind the scenes and which steps are necessary to translate an experiment.


Internationalization process
++++++++++++++++++++++++++++

All PsyNet internationalization relies on ``gettext`` which is a common tool for internationalization.
There are basically four steps to translate an experiment:

1. Marking strings for translation
2. Extracting the strings into a template file (``.pot``)
3. Translating the strings into a ``.po`` file
4. Compiling the ``.po`` file into a machine-readable ``.mo`` file

PsyNet automatically handles all four steps.
While PsyNet relies on two commonly used machine translators, we recommend to have a native speaker check the translations.



Install ``gettext``
-------------------
Run the following command to install ``gettext`` on your system:

::

   $ sudo apt-get install gettext # for Ubuntu-based distributions
   $ brew install gettext # for macOS


Mark strings for translation
----------------------------

In order to translate the experiment, one needs to mark which strings
need to be translated. ``gettext`` will search for those strings in the
respective files and will create a ``.pot`` file. ``gettext`` by default
will look for ``gettext`` and its alias ``_``. Let’s try it for this Python snippet in a file called ``example.py``:

::

   from gettext import gettext

   _ = gettext
   my_info_page = InfoPage(
        Markup(
            f"""
            <h1>{_("Instructions")}</h1>
            <hr>
            {_("In this experiment, you will listen to different music clips.")} <br>
            {_("You have to select the music you like most.")}
            """
        ),
        time_estimate=5
    )


In PsyNet we use a wrapper for this:

::

    import os

    from markupsafe import Markup
    from psynet.page import InfoPage
    from psynet.utils import get_translator

    locale = "nl"
    _ = get_translator()

    my_info_page = InfoPage(
        Markup(
            f"""
            <h1>{_("Instructions")}</h1>
            <hr>
            {_("In this experiment, you will listen to different music clips.")} <br>
            {_("You have to select the music you like most.")}
            """
        ),
        time_estimate=5
    )

Most experiments only use ``_``, which is an alias of ``gettext``.
Additionally, there is also ``_p`` (alias of ``pgettext``, ``_p = get_translator_with_context()``) which takes the context a translation occurs in and the string which has to be translated. This is useful to disambiguate the same string in different contexts. For example, the word "play" can be a verb or a noun. In English, the translation would be the same, but in other languages, it might be different. In this case, we would use ``_p`` to mark the strings for translation.

However, adding a cumbersome to each string can be quite cumbersome. We, therefore, recommend to use ``_p`` only for strings that are ambiguous and need to be disambiguated (quite often you do not use the same word in different contexts).

The same mechanism works for HTML templates:

Extracting and marking the translatable strings in PsyNet are the same as for any other Python script. For Jinja2 templates (HTML files), you can use:

::

    {{ gettext("Unfortunately the experiment must end early.") }}


Or if you want to disambiguate the string, you can use:

::

    {{ pgettext('final_page_unsuccessful', "Unfortunately the experiment must end early.") }}


Extracting the strings into a template file (``.pot``)
------------------------------------------------------

The next step is to create the PO Template (``.pot``) file. This can be done manually by running the following command in the directory where the ``example.py`` file is located:

::

   xgettext -d experiment -o locales/experiment.pot example.py

The ``xgettext`` command consists of three arguments:

1. ``-d`` indicating the name of the module. Modules are like namespaces, for example, translations in PsyNet will use the module ``psynet``. For experiments, we recommend using the module name ``experiment``
2. Translation files are stored in the ``locales`` folder. Make sure you have created one in your experiment. You can do this by running

::

   mkdir locales

in your experiment directory.

3. Finally, you need to pass in the file. Here we use one file (``example.py``), but you can add multiple files, e.g. all Python files in a folder:

::

   xgettext -d experiment -o locales/experiment.pot *.py

With ``-L`` you can optionally specify the programming language,
e.g. ``-L Python``.

In PsyNet, we use a wrapper for this:

::

    create_pot(
        input_folder, pot_path
    )

Which looks for all in the folder and extracts the strings into the ``.pot`` file ``pot_path``.

However, when using PsyNet you can use the high-level API:

::

    psynet translate


which will:

- Create the ``.pot`` file
- Perform machine translation to all languages supported by the package or those marked in ``supported_locales`` in your config or those marked manually ``psynet translate nl de``
- Automatically check the translations

PO format
---------

Let’s have a look at the PO format by opening
``locales/experiment.pot``. You can see a lot of entries starting with
``msgid`` and ``msgstr``. The first entry looks like this and has meta-information
about the translation:

::

   msgid ""
   msgstr ""
   "Project-Id-Version: PACKAGE VERSION\n"
   "Report-Msgid-Bugs-To: \n"
   "POT-Creation-Date: 2022-11-17 10:43+0100\n"
   "PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
   "Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
   "Language-Team: LANGUAGE <LL@li.org>\n"
   "Language: \n"
   "MIME-Version: 1.0\n"
   "Content-Type: text/plain; charset=CHARSET\n"
   "Content-Transfer-Encoding: 8bit\n"

The other entries start with a comment where it occurs in the code
followed by a ``msgid`` (key, string to be translation) and ``msgstr`` (value, this is where the translation goes):

::

   #: example.py:8
   msgid "Instructions"
   msgstr ""

PO files
--------

The ``.po`` files are created from ``.pot`` files and are identical in
structure. The translations will replace the empty string in ``msgstr``
with the translation. This means that for every language that you want
your experiment to be translated to, you need to create a ``.po`` file
from the main ``.pot`` file. Translations will be stored in:

::

   locales/<ISO_LANG>/LC_MESSAGES/<module>.po

Create the ``locales`` folder that will contain all translations
(e.g., ``de``, ``el``). This folder must contain a subfolder ``LC_MESSAGES`` (this folder naming
is mandatory) which in turn contains the ``.po`` and the compiled translations (``.mo`` files).


Translating the strings into a ``.po`` file
-------------------------------------------

Let’s translate into Greek; ``cd`` into the experiment folder and run:

::

   psynet translate el

.. note::
    ``el`` is the ISO code for Greek, see `here <https://www.gnu.org/software/gettext/manual/html_node/Usual-Language-Codes.html>`__ for full list

You can now open the resulting ``.po`` file with `POedit editor <https://poedit.net>`__ and check the translations. Unchecked translations are flagged. Unflag them once you checked them.

Combining translations
----------------------

To update the translations, you can run ``psynet translate``, which will update the ``.pot`` file and will provide new translations and overwrite the existing translations unless they were marked as checked.

Compiling the ``.po`` file into a machine-readable ``.mo`` file
---------------------------------------------------------------

In PsyNet translations are compiled on demand. This means that if you add a new translation, you do not have to compile the translations.

Setting the language
--------------------

To load the translation, you need to access the current participant as language settings are attached to a participant. By default the participant language is set to the language of the experiment, which can be set in ``config.txt``:

::

   locale = <your_language_iso_code>

- Supported languages the user can choose from

::

   supported_locales = ["en", "de", "nl"]

-  The ability for the participant to change the language during the experiment

::

   allow_switching_locale = True

It is always possible to programmatically overwrite the language of the
user by overwriting ``participant.var.locale``. To access the ``participant`` variable in the timeline, you can use :class:`~psynet.timeline.PageMaker`.

To see the translation in action, have a look at the ``translation`` demo.


Design choices
++++++++++++++

There are a few design choices that we made when implementing the translation system in PsyNet. We will explain these choices and the reasoning behind them.

- Language is set on the level of the experiment. The participant inherits this language setting. The translation shown to the participant depends on the participants' language setting. The idea behind is that you can have multilingual experiments, where individual participants do the experiment in different languages. This also allows participants to potentially switch between languages during the experiment.
- Variables in translatable strings can be error prone as they might not be translated properly which can lead to runtime errors. PsyNet automatically checks them in a predeploy routine before starting the experiment. To minimize error, we have strong variable naming rules. You may only use f-string notation where the variable name only consists of capital letters and underscores. So ``_("My variable: {MY_VARIABLE}")`` would be allowed, but ``_("My variable: {my_variable}")`` or ``_("My variable: {}")`` would not. This is because the capital letters are less likely to be translated into the target language by machine translation. They are also more visible to human translators. You can also only use ``.format()`` and not f-strings as the latter will replace the variable before looking up the translation. Say ``"This is your {AGE}"`` is a defined translation, ``"This is your 12"`` is probably not! So the correct way to use variables in translations is ``_("This is your {AGE}").format(AGE=12)``.
- Translations are structured into modules. Each module should have distinct name. So PsyNet has a separate module called ``psynet`` and the experiment called ``experiment``. Each package is responsible for the text in their package, so PsyNet stores all translations in ``psynet/locales``, where the template is stored in ``psynet/locales/psynet.pot`` and the translations are stored in ``psynet/locales/<language_code>/LC_MESSAGES/psynet.po``. The same is true for the experiment, where the template is stored in ``<experiment_dir>/locales/experiment.pot`` and the translations are stored in ``<experiment_dir>/locales/<language_code>/LC_MESSAGES/experiment.po``.
- Translations of the experiment are checked automatically in a predeploy route. Translations of psynet are checked using CI.
