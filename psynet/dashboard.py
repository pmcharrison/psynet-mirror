import dallinger.models
from dallinger.experiment_server import dashboard

from .timeline import Response
from .trial.main import Trial


def patch_dashboard_models():
    "Determines the list of objects in the dashboard database browser."
    dallinger.models.Trial = Trial
    dallinger.models.Response = Response

    dashboard.BROWSEABLE_MODELS = [
        "Participant",
        "Network",
        "Node",
        "Trial",
        "Response",
        "Transformation",
        "Transmission",
        "Notification",
    ]


patch_dashboard_models()


def show_in_dashboard(cls):
    """
    This decorator can be applied to any custom SQLAlchemy object
    to show it as a selectable category in the dashboard.
    For example:

    ::

        @show_in_dashboard
        class Bird(Base, SharedMixin):
            __tablename__ = "bird"

    """
    setattr(dallinger.models, cls.__name__, cls)
    dashboard.BROWSEABLE_MODELS.append(cls.__name__)
    return cls
