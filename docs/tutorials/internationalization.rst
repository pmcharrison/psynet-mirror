====================
Internationalization
====================

PsyNet makes it easy to create novel paradigms and test them on a large
scale. Ideally, one can test the paradigm with participants from all
over the world. This requires translation of the experiment into the
respective language.

Internationalization in general
===============================
To translate PsyNet experiments, we will use standard software to handle translations.
We'll use the ``gettext`` software. In a nutshell, we use the software to scan translatable strings indicated by the programmer. The strings are then stored in a file as key value pairs, where the keys are the original sentences and the values are blank and need to be completed by a translator. The translated strings are then compiled into a binary file, which is used by the program.

Let’s install ``gettext``:

::

   $ sudo apt-get install gettext # for Ubuntu-based distributions
   $ brew install gettext # for macOS


How does ``gettext`` work?
--------------------------

In order to translate the experiment, one needs to mark which strings
need to be translated. ``gettext`` will search for those strings in the
respective files and will create a ``.pot`` file. ``gettext`` by default
will look for ``gettext`` and its alias ``_``. Let’s try it for this Python snippet in a file called ``example.py``:

::

   from gettext import gettext
   _ = gettext
   my_info_page = InfoPage(
           Markup(
           '<h1>' + _("Instructions") + '</h1>' +
           '<hr>'+
           '<p>'+
           '%s <br>'%(_('In this experiment, you will listen to sounds by moving a slider.'))+
               _('You will be asked to pick the sound which best represents a property in question.')+
           '</p>'+
           '<img src="/static/images/slider_example.png" alt="Schematic figure of experimental task" style="width:450px">'+
           '<hr>'
           ),
           time_estimate=10
   )

POT file
~~~~~~~~

We can create the PO Template (``.pot``) file by running the following command in the directory where the ``example.py`` file is located:

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
e.g. ``-L Python``.

PO format
~~~~~~~~~

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

Compiling the translation
-------------------------

In order to use the translation in PsyNet (or in any other code), we have to convert
the ``.po`` file to a machine-readable translation ``.mo``-file. You can
do so by running:

::

   msgfmt -o locales/el/LC_MESSAGES/experiment.po locales/el/LC_MESSAGES/experiment.mo

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

    #: /Users/pol.van-rijn/psynet-package/psynet/demography/general.py:145
    #, fuzzy
    msgctxt "gender"
    msgid "Female"
    msgstr "Weiblich"

Make sure to double check the translation before compiling, because gettext in Python `does not show` fuzzy translations. Also note that ``msgmerge`` removes keys that are not in the updated file (e.g., you might loose translations which were commented out). Lastly, keep in
mind that the order of the files in this command matters.

Contexts, variables, and numbers
--------------------------------

We now know the basics about ``gettext``, but it can do way more. One feature is called 'context' which you can pass along with your translation. A context disambiguates a translation with the same key which occurs in a different context. For example, consider the word “print”. In most contexts, this word refers to printing something (e.g., using a printer), but in another context, it might mean displaying something, e.g. (``print("Hello!")``). In those situations, one should use contexts. This can be done with ``pgettext('my-context', 'print')``. I would recommend *always* adding context as it will help you disambiguate meanings and is useful information for the translator. There’s a few exceptions, e.g., for words such as “Yes” or “Next” which usually have the same translation regardless of the context.

Another consideration is how to display variables in translations. The general advice is to avoid variable names in translations where possible, as translators can forget to mark the variable in the translation leading to a runtime error. If you are using variables in translations, we encourage to use fstrings. However, we recommend using capital variable names, e.g. ``"This is your {AGE}"`` instead of ``"This is your {age}"`` as the uppercase letters are less likely to be translated into the target language. Furthermore, you **should only use** use ``"This is your {AGE}".format(AGE=12)`` and NOT ``f"This is your {AGE}"`` as the second command will replace the variable in the string before looking up the translation. Where ``"This is your {AGE}"`` is a defined translation, ``"This is your 12"`` is probably not!

Plural forms are highly language dependent, so this it is strongly *discouraged* to use in gettext. Instead it's better to write a separate translation for each condition separately, i.e.:

::

    if score < 10:
        msg = pgettext("feedback", "Sorry, your score was too low and you have to leave the experiment early.")
    else:
        msg = pgettext("feedback", "Congratulations! You passed the test.")

Use high-level tools where possible!
------------------------------------

Making mistakes in translations is easy and small mistakes in a translation can easily lead to runtime errors which are hard to catch without running the program (e.g., the string might expect a variable, but the translator forgot to mark it). Therefore, it is recommended to use high-level tools and not do the translation in a text editor.


We recommend using `POedit editor <https://poedit.net>`__ which warns the user about many potential issues in the translation. By saving a PO file, it will also automatically compile a MO file.

.. warning::
    However, before saving the file with POedit or compiling it manually, you need to make sure that none of the strings are flagged as fuzzy (the translation entry would be marked as “Needs work”). If you don’t remove them, the translations for those strings will not be recognized.


Translating a PsyNet experiment
===============================
Now that we know the basics of ``gettext``, we can start translating our experiment.

Loading the translation
-----------------------

Extracting and marking the translatable strings in PsyNet are the same as for any other Python script. For Jinja2 templates (HTML files), you can use:

::

    {{ pgettext('final_page_unsuccessful', "Unfortunately the experiment must end early.") }}


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
