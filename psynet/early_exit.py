"""Domain models shared by voluntary Leave and fatal-error recovery.

Recruiters decide which platform-specific path an early exit follows, while
this module defines the plan and presentation data that cross the
recruiter/experiment/browser boundary. Keeping these value objects independent
of recruiter implementations makes their serialization and lifecycle rules
easy to reuse without importing the large recruiter integration module.
"""

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from dallinger.config import get_config


@dataclass(frozen=True)
class EarlyExitConfirmation:
    """Participant-facing copy contained in an early-exit plan.

    Parameters
    ----------
    title
        Dialog heading.
    message
        Explanation of what leaving means for this recruiter and payment setup.
    confirm_label
        Label for the button that confirms Leave.
    cancel_label
        Label for the button that continues participation.
    """

    title: str
    message: str
    confirm_label: str
    cancel_label: str


class EarlyExitContext(StrEnum):
    """Why PsyNet is preparing an early-exit plan."""

    VOLUNTARY = "voluntary"
    ERROR_RECOVERY = "error_recovery"


class EarlyExitPath(StrEnum):
    """Platform path for confirmed Leave or automatic error recovery."""

    END_SESSION = "end_session"
    SCREEN_OUT = "screen_out"
    RETURN_FOR_BONUS = "return_for_bonus"
    RETURN_WITHOUT_PAYMENT = "return_without_payment"
    TERMINATE_PANEL_SESSION = "terminate_panel_session"


@dataclass(frozen=True)
class ErrorRecoveryPresentation:
    """Recruiter-specific copy and handoff for an error page."""

    message: str
    failure_message: str | None = None
    researcher_contact_message: str | None = None
    button_label: str | None = None
    preparation_post_url: str | None = None
    preparation_post_data: dict[str, str] = field(default_factory=dict)
    action_post_url: str | None = None
    action_post_data: dict[str, str] = field(default_factory=dict)
    destination_url: str | None = None
    auto_redirect_delay_ms: int | None = None

    def __post_init__(self):
        """Reject presentations whose declared handoff cannot be executed."""
        if self.preparation_post_data and not self.preparation_post_url:
            raise ValueError("Preparation POST data requires a URL.")
        if self.action_post_data and not self.action_post_url:
            raise ValueError("Action POST data requires a URL.")
        if (self.action_post_url or self.destination_url) and not self.button_label:
            raise ValueError("A participant handoff requires a button label.")
        if self.auto_redirect_delay_ms is not None:
            if self.auto_redirect_delay_ms <= 0:
                raise ValueError("An automatic redirect delay must be positive.")
            if not self.destination_url:
                raise ValueError("An automatic redirect requires a destination URL.")


@dataclass(frozen=True)
class EarlyExitPlan:
    """Server-owned early-exit offer and execution plan.

    Plans live only as long as the participant's session, so there is no
    schema versioning here; :meth:`from_dict` simply refuses anything it cannot
    read as a plan.
    """

    offer_id: str
    context: EarlyExitContext
    path: EarlyExitPath
    status: str
    confirmation: EarlyExitConfirmation
    quoted_amounts: dict[str, str | int] = field(default_factory=dict)
    quoted_amounts_complete: bool = True

    @classmethod
    def create(
        cls,
        *,
        context: EarlyExitContext,
        path: EarlyExitPath,
        confirmation: EarlyExitConfirmation,
        quoted_amounts: dict[str, str | int] | None = None,
        quoted_amounts_complete: bool = True,
    ) -> "EarlyExitPlan":
        """Create a new offered plan."""
        return cls(
            offer_id=str(uuid4()),
            context=context,
            path=path,
            status="offered",
            confirmation=confirmation,
            quoted_amounts=dict(quoted_amounts or {}),
            quoted_amounts_complete=quoted_amounts_complete,
        )

    def to_dict(self) -> dict:
        """Return a primitive dictionary suitable for participant storage."""
        data = asdict(self)
        data["context"] = self.context.value
        data["path"] = self.path.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "EarlyExitPlan":
        """Restore a plan from participant storage."""
        if data.get("status") not in {"offered", "executed"}:
            raise ValueError("Invalid early-exit plan status.")
        return cls(
            offer_id=data["offer_id"],
            context=EarlyExitContext(data["context"]),
            path=EarlyExitPath(data["path"]),
            status=data["status"],
            confirmation=EarlyExitConfirmation(**data["confirmation"]),
            quoted_amounts=dict(data.get("quoted_amounts", {})),
            quoted_amounts_complete=data.get("quoted_amounts_complete", True),
        )

    def mark_executed(self) -> "EarlyExitPlan":
        """Return an executed copy of this plan."""
        return replace(self, status="executed")


def _format_early_exit_amount(amount: float) -> str:
    """Format a currency amount for early-exit confirmation copy."""
    currency = get_config().get("currency", "$")
    return f"{currency}{float(amount):.2f}"


def _format_quoted_early_exit_amount(plan: EarlyExitPlan, name: str) -> str:
    """Format one amount stored in an early-exit plan."""
    amount = plan.quoted_amounts[f"{name}_minor"] / 100
    currency = plan.quoted_amounts.get("currency")
    if currency is None:
        currency = get_config().get("currency", "$")
    return f"{currency}{amount:.2f}"


def _early_exit_amounts(**amounts) -> dict:
    """Store quoted currency amounts as integer minor units."""
    return {
        "currency": get_config().get("currency", "$"),
        **{
            f"{name}_minor": int(Decimal(f"{float(value):.2f}") * 100)
            for name, value in amounts.items()
        },
    }


def _early_exit_quoted_amount(plan: EarlyExitPlan, name: str) -> float:
    """Read one quoted amount from an early-exit plan."""
    return plan.quoted_amounts[f"{name}_minor"] / 100


def _executed_early_exit_plan(participant) -> EarlyExitPlan | None:
    """Return the participant's executed early-exit plan, if present."""
    data = getattr(participant, "early_exit_plan", None)
    if not isinstance(data, dict):
        return None
    try:
        plan = EarlyExitPlan.from_dict(data)
    except (KeyError, TypeError, ValueError):
        return None
    if plan.status != "executed" or not bool(participant.early_exited):
        return None
    return plan


def _early_exit_returns_without_payment(participant) -> bool:
    """Return whether the stored plan records an exit without payment."""
    plan = _executed_early_exit_plan(participant)
    return plan is not None and plan.path is EarlyExitPath.RETURN_WITHOUT_PAYMENT
