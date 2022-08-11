import os

# Registering SQLAlchemy and jsonpickle handlers -
# not enforcing this can give us some hairy bugs in our regression tests
from . import asset, data, field, serialize, trial  # noqa
from .trial import chain, dense, main  # noqa

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "VERSION")) as version_file:
    __version__ = version_file.read().strip()


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
#         self.register("export_root", unicode)
#
#     Configuration.register_extra_parameters = register_extra_parameters
#
# patch_dallinger_config()
