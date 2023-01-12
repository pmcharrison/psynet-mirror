from psynet.version import check_dallinger_version

check_dallinger_version()

# To make sure the tests run properly (in particular, avoiding errors
# where one test breaks the test that runs after it),
# it is essential to always import ALL modules that define SQLAlchemy
# classes whenever the PsyNet package is imported.
# Not enforcing this can give us some hairy bugs in our regression tests,
# things like queries unexpectedly returning no items even though
# we can see those items in the database.
from . import (  # noqa
    asset,
    bot,
    data,
    error,
    field,
    participant,
    prescreen,
    process,
    serialize,
    trial,
    version,
)
from .trial import (  # noqa; graph,  # temporarily commented out so we can test other parts of the codebase before refactoring this
    audio,
    audio_gibbs,
    chain,
    dense,
    imitation_chain,
    main,
    mcmcp,
    record,
    static,
    video,
)

__version__ = version.psynet_version


# def patch_dallinger_config():
#     from dallinger.compat import unicode
#     from dallinger.config import Configuration
#
#     def register_extra_parameters(self):
#         """
#         The Dallinger version additionally looks for extra parameters defined on the
#         experiment class. However this requires initializing the experiment
#         package which can cause annoying SQLAlchemy bugs. We therefore override this.
#         """
#         self.register("cap_recruiter_auth_token", unicode)
#         self.register("lucid_api_key", unicode)
#         self.register("lucid_sha1_hashing_key", unicode)
#         self.register("lucid_recruitment_config", unicode)
#         self.register("default_export_root", unicode)
#
#     Configuration.register_extra_parameters = register_extra_parameters
#
# patch_dallinger_config()
