import sys

from dallinger.config import get_config
from dallinger.models import (
    Info,
    Network,
    Node,
    Notification,
    Participant,
    Question,
    Transformation,
    Transmission,
    Vector,
)

def export(class_name):
    """
    Export data from an experiment.

    Collects instance data for class_name, including inheriting models.
    """
    config = get_config()
    if not config.ready:
        config.load()

    models = {}
    instances = getattr(sys.modules[__name__], class_name).query.all()
    for instance in instances:
        model = instance.__class__.__name__
        if not model in models:
            models[model] = []
            models[model].append(instance.__json__())
        else:
            models[model].append(instance.__json__())
    return models
