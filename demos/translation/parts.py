import gettext
import os
from psynet.utils import get_language

LANGUAGE = get_language()
domain_name = os.path.basename(__file__)[:-3] # strip .py 
lang = gettext.translation(domain_name, localedir='locale', languages=[LANGUAGE])
lang.install()

# These translated strings are imported into the main experiment
textLib = {}
textLib["info_translation_1"] = _("Imported and translated text!")
textLib["info_translation_2"] = _("Here is a another line for translation!")
