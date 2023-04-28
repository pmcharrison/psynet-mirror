====================
Internationalization
====================

Finally, you created an amazing experiment! How cool would it be to run it with participants from all over the world?

Luckily, PsyNet makes it easy to run experiments in different languages. Here's what you need to do:


Mark which strings need to be translated
========================================
Let's say you have the following info page in your experiment:


::

    from flask import Markup
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


::

    import os

    from flask import Markup
    from psynet.page import InfoPage
    from psynet.utils import get_translator

    locale = "nl"
    _, _p = get_translator(
        locale, module="experiment", locales_dir=os.path.abspath("locales")
    )
    my_info_page = InfoPage(
        Markup(
            f"""
            <h1>{_p("instruction", "Instructions")}</h1>
            <hr>
            {_p("instruction", "In this experiment, you will listen to different music clips.")} <br>
            {_p("instruction", "You have to select the music you like most.")} <br>
            {_('Press "Next" to continue.')}
            """
        ),
        time_estimate=5
    )


``gettext`` is a software that is used to handle translations. PsyNet, like most translated software, use it.

In a nutshell, you need two functions ``gettext`` (aka ``_``) and ``pgettext`` (aka ``_p``).


If you want to be more verbose, you can also write:

::
    gettext, pgettext = get_translator(
        locale, module="experiment", locales_dir=os.path.abspath("locales")
    )

You should mainly use mainly use ``pgettext`` as it tell you (the programmer) and the translator more precisely in which context the translation occurs. It helps to disambiguate between possible translations.

The only case where you should use ``gettext`` is when you have a string that is used in multiple contexts. For example, if you have a string that is used in multiple pages (e.g., ``_('Press "Next" to continue.')``), you should use ``gettext``.

If you want to use a variable in the translation specify it as follows:

::

    next_button_name = _("Next")
    next_button_text = _('press "{NEXT_BUTTON_NAME}" to continue.').format(NEXT_BUTTON_NAME=next_button_name)

Note that variables in the translation may only consist of capital letters and underscores, are surrounded by curly brackets and must be replaced with the ``.format`` method (f-strings are not allowed). You can read more about translation in the section `Internationalization in general`_.


Extract the translations
========================
Open a terminal in your experiment folder and run the following command:

::

    psynet prepare-translation <iso_code>


This will create a file ``locales/<iso_code>/LC_MESSAGES/experiment.po``. You can open it with `POedit editor <https://poedit.net>`__ and see that it contains the strings that you marked with ``_`` and ``_p``. Go ahead and translate them!

Set the correct language
========================
Finally, you need to tell PsyNet which language to use. You can do this by setting


::

   language = <your_language_iso_code>

in your ``config.txt`` file. PsyNet will then automatically load the correct translation. That's it!

To see the translation in action, have a look at the ``translation`` demo.
