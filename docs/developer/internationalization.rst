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

PsyNet automatically handles steps 1, 2, and 4. Step 3 can be partly be automized using machine translation (see third-party package `internat <https://gitlab.com/computational-audition-lab/internationalization>`_), nevertheless we recommend to have a native speaker check the translations.



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
    _, _p = get_translator(
        locale, module="experiment", locales_dir=os.path.abspath("locales")
    )

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

Here you see two ways to mark strings for translation. The first one is ``_`` which is an alias of ``gettext`` and the second one is ``_p`` (alias of ``pgettext``) which takes the context a translation occurs in and the string which has to be translated. This is useful to disambiguate the same string in different contexts. For example, the word "play" can be a verb or a noun. In English, the translation would be the same, but in other languages, it might be different. In this case, we would use ``_p`` to mark the strings for translation.

The same mechanism works for HTML templates:

Extracting and marking the translatable strings in PsyNet are the same as for any other Python script. For Jinja2 templates (HTML files), you can use:

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
        input_folder, "path/to/my/files/*.html", pot_path
    )

Which looks for all HTML files in the folder ``f"{input_folder}/path/to/my/files"`` and extracts the strings into the ``.pot`` file ``pot_path``.

We provide a default extraction script for the PsyNet package ``create_psynet_translation_template()`` and for experiment folder ``Experiment.create_translation_template_from_experiment_folder()``.

While this probably works for most experiments (it scans all .py files in the experiment directory and the templates folder if it exists), it can be easily extended to scan other subdirectories:

::

    class Exp(psynet.experiment.Experiment):
        @classmethod
        def create_translation_template_from_experiment_folder(cls, input_directory, pot_path):
            super(Exp, cls).extract_pot_from_experiment_folder(input_directory, pot_path)

            from psynet.internationalization import create_pot

            create_pot(input_directory, "my_module/.", pot_path)

We also provide a command line interface to extract the strings: ``psynet prepare-translation <iso_code>``.

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

Let’s translate into Greek. We first have to set up a
folder for the Greek translation file (``el`` is the ISO code for Greek,
see
`here <https://www.gnu.org/software/gettext/manual/html_node/Usual-Language-Codes.html>`__
for full list):

::

   mkdir -p locales/el/LC_MESSAGES

We now have to copy the template to the directory:

::

   cp locales/experiment.pot locales/el/LC_MESSAGES/experiment.po

Open this file and add the translation to ``msgstr``:

::

   #: example.py:8
   msgid "Instructions"
   msgstr "Οδηγίες"


A better way of doing this is to copy the ``.pot`` file to ``locales/<your_language>/LC_MESSAGES/experiment.po`` and open it with `POedit editor <https://poedit.net>`__.

You can also use the package `internat <https://gitlab.com/computational-audition-lab/internationalization>`_ to create machine translation using Google Translate and DeepL for a ``.pot`` file. Note this package is still work in progress. To translate a ``.pot`` file you would run:

::

    from internat.translate import translate_pot

    translate_pot(
        pot_path,
        input_language="en",
        output_language=target_language,
        translator="DeepL",
        formality="formal",
    )


Note you should open the resulting ``.po`` file with `POedit editor <https://poedit.net>`__ and check the translations. Unchecked translations are flagged. Unflag them once you checked them. Otherwise they will not compile.

Combining translations
----------------------

Many times you will have to update a translation because new strings are added, modified or removed. To manipulate the translation files and keep them updated, you can use the ``msgcat`` and ``msgmerge`` commands. We will now have a quick look at them.

::

    msgcat filename_1.po filename_2.po -o output.po

Given two .po files, ``msgcat`` concatenates these two files into a single one.

.. note::

    If the same key exists within both files but with different translations, then ``msgcat`` adds both translations to the new file and the translator should fix the conflict.

::

    msgmerge previous.po updated.po -o output.po [--no-fuzzy-matching]``

To merge two translations, you can use ``msgmerge``. Imagine you created a new PO file from all of your translatable strings from your code called ``updated.po``, but you already have the translations for a large part of the code in ``previous.po``. You can use ``msgmerge`` to only add the new entries of ``updated.po`` to ``previous.po`` and store the result in the final ``output.po`` file. The optional argument ``--no-fuzzy-matching`` will prevent the merging of fuzzy translations. Fuzzy matching means that it will not look for a 100% match, but will also match keys which changed slightly. Fuzzy matched translations will be flagged with the keyword ``fuzzy``:

::

    #: psynet/demography/general.py:145
    #, fuzzy
    msgctxt "gender"
    msgid "Female"
    msgstr "Weiblich"


In practice, it turned out if a translation only changed minimally, it's fastest to simply do a text search over the ``.po`` files.

Compiling the ``.po`` file into a machine-readable ``.mo`` file
---------------------------------------------------------------

In PsyNet translations are compiled on demand. This means that if you add a new translation, you do not have to compile the translations. Also, PsyNet makes sure fuzzy translations (i.e. unvalidated translations) are unflagged so they are shown in the experiments.

If you would want to compile the translations manually, you can do so by running:

In order to use the translation in PsyNet (or in any other code), we have to convert
the ``.po`` file to a machine-readable translation ``.mo``-file. You can
do so by running:

::

   msgfmt -o locales/el/LC_MESSAGES/experiment.po locales/el/LC_MESSAGES/experiment.mo

Make sure to double check the translation before compiling, because gettext in Python `does not show` fuzzy translations. Also note that ``msgmerge`` removes keys that are not in the updated file (e.g., you might loose translations which were commented out). Lastly, keep in
mind that the order of the files in this command matters.

Setting the language
--------------------

To load the translation, you need to access the current participant as language settings are attached to a participant. By default the participant language is set to the language of the experiment, which can be set in ``config.txt``:

::

   language = <your_language_iso_code>

To get the translation from the participant, we can run:

::

   from os.path import abspath
   from psynet.utils import get_translator

   _, _p, _np = get_translator(
       locale = participant.get_locale(),
       module='experiment',
       localedir=abspath('locales')
   )


Note that ``_`` is an alias for ``gettext`` and ``_p`` for ``pgettext``. ``participant.get_locale()`` will return the
language settings of a participant.

You can also set additional language settings in the config:

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
- ``gettext`` provides various ways to translate strings, ``gettext`` simple key value, ``pgettext`` translation within a context and ``ngettext`` for plural forms. Then there are also all combinations of them. We decided to only use ``gettext`` and ``pgettext`` and not use any of the other functions. The reason is that plural forms are highly language dependent and it is not possible to write a generic function that works for all languages. Instead, we recommend to write separate translations for each condition.
- Variables in translatable strings can be error prone as they might not be translated properly which can lead to runtime errors. PsyNet automatically checks them in a predeploy routine before starting the experiment. To minimize error, we have strong variable naming rules. You may only use f-string notation where the variable name only consists of captial letters and underscores. So ``_("My variable: {MY_VARIABLE}")`` would be allowed, but ``_("My variable: {my_variable}")`` or ``_("My variable: {}")`` would not. This is because the captial letters are less likely to be translated into the target language by machine translation. They are also more visible to human translators. You can also only use ``.format()`` and not f-strings as the latter will replace the variable before looking up the translation. Say ``"This is your {AGE}"`` is a defined translation, ``"This is your 12"`` is probably not! So the correct way to use variables in translations is ``_("This is your {AGE}").format(AGE=12)``.
- Translations are structured into modules. Each module should have distinct name. So PsyNet has a separate module called ``psynet`` and the experiment called ``experiment``. Each package is responsible for the text in their package, so PsyNet stores all translations in ``psynet/locales``, where the template is stored in ``psynet/locales/psynet.pot`` and the translations are stored in ``psynet/locales/<language_code>/LC_MESSAGES/psynet.po``. The same is true for the experiment, where the template is stored in ``<experiment_dir>/locales/experiment.pot`` and the translations are stored in ``<experiment_dir>/locales/<language_code>/LC_MESSAGES/experiment.po``.
- Translations of the experiment are checked automatically in a predeploy route. Translations of psynet are checked using CI.
