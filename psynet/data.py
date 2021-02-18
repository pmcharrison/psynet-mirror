import sys

from dallinger.models import Info  # noqa
from dallinger.models import Network  # noqa
from dallinger.models import Node  # noqa
from dallinger.models import Notification  # noqa
from dallinger.models import Participant  # noqa
from dallinger.models import Question  # noqa
from dallinger.models import Transformation  # noqa
from dallinger.models import Transmission  # noqa
from dallinger.models import Vector  # noqa


def export(class_name):
    """
    Export data from an experiment.

    Collects instance data for class_name, including inheriting models.
    """
    models = {}
    instances = getattr(sys.modules[__name__], class_name).query.all()
    for instance in instances:
        model = instance.__class__.__name__
        if model not in models:
            models[model] = []
            models[model].append(instance.__json__())
        else:
            models[model].append(instance.__json__())
    return models
