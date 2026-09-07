"""Domain models for participant exit planning.

Every terminal participant outcome has the same core concerns: PsyNet records
why the session ended, recruiters choose a platform handoff, and payment is
planned before any external transfer occurs.  This module contains the value
objects shared by normal completion, unsuccessful completion, voluntary Leave,
and fatal-error recovery.  Timeline and error-page code remain responsible for
presenting those outcomes appropriately.
"""

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from uuid import uuid4

from dallinger.config import get_config


@dataclass(frozen=True)
class PaymentDecision:
    """Describe intended participant payment before spend caps or transfer.

    Parameters
    ----------
    status
        Recruitment-platform outcome, such as ``approved`` or ``screened_out``.
    platform_base
        Amount supplied by the recruitment platform.
    bonus
        Additional amount PsyNet intends to transfer.
    """

    status: str
    platform_base: float
    bonus: float

    @classmethod
    def from_dict(cls, data: dict) -> "PaymentDecision":
        """Restore a payment decision from primitive participant data."""
        return cls(
            status=data["status"],
            platform_base=float(data["platform_base"]),
            bonus=float(data["bonus"]),
        )


@dataclass(frozen=True)
class EarlyExitConfirmation:
    """Participant-facing copy for a voluntary Leave offer."""

    title: str
    message: str
    confirm_label: str
    cancel_label: str


class ExitContext(StrEnum):
    """Reason that a participant is leaving the experiment."""

    SUCCESSFUL = "successful"
    UNSUCCESSFUL = "unsuccessful"
    VOLUNTARY = "voluntary"
    ERROR_RECOVERY = "error_recovery"
    REJECTED_CONSENT = "rejected_consent"


class ExitPath(StrEnum):
    """Recruiter handoff selected for a participant exit."""

    END_SESSION = "end_session"
    SCREEN_OUT = "screen_out"
    RETURN_FOR_BONUS = "return_for_bonus"
    RETURN_WITHOUT_PAYMENT = "return_without_payment"
    TERMINATE_PANEL_SESSION = "terminate_panel_session"


class ExitPlanStatus(StrEnum):
    """Lifecycle state of a stored exit plan."""

    PREPARED = "prepared"
    COMMITTED = "committed"


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
class ExitPlan:
    """Server-owned plan for one participant's terminal outcome.

    ``payment_is_final`` is false only when error recovery could determine the
    platform outcome but could not calculate the complete reward.  Settlement
    then asks the recruiter to complete the decision from persisted participant
    data before transferring money.
    """

    plan_id: str
    context: ExitContext
    path: ExitPath
    status: ExitPlanStatus
    payment: PaymentDecision | None
    currency: str
    confirmation: EarlyExitConfirmation | None = None
    payment_is_final: bool = True

    @classmethod
    def create(
        cls,
        *,
        context: ExitContext,
        path: ExitPath,
        payment: PaymentDecision | None,
        confirmation: EarlyExitConfirmation | None = None,
        payment_is_final: bool = True,
        currency: str = "$",
    ) -> "ExitPlan":
        """Create a prepared exit plan."""
        return cls(
            plan_id=str(uuid4()),
            context=context,
            path=path,
            status=ExitPlanStatus.PREPARED,
            payment=payment,
            currency=currency,
            confirmation=confirmation,
            payment_is_final=payment_is_final,
        )

    def to_dict(self) -> dict:
        """Return primitive data suitable for participant storage."""
        data = asdict(self)
        data["context"] = self.context.value
        data["path"] = self.path.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ExitPlan":
        """Restore an exit plan from participant storage."""
        try:
            status = ExitPlanStatus(data["status"])
        except ValueError as exc:
            raise ValueError("Invalid exit plan status.") from exc
        confirmation = data.get("confirmation")
        payment = data.get("payment")
        return cls(
            plan_id=data["plan_id"],
            context=ExitContext(data["context"]),
            path=ExitPath(data["path"]),
            status=status,
            payment=(
                None if payment is None else PaymentDecision.from_dict(payment)
            ),
            currency=data.get("currency", "$"),
            confirmation=(
                None
                if confirmation is None
                else EarlyExitConfirmation(**confirmation)
            ),
            payment_is_final=data.get("payment_is_final", True),
        )

    def mark_committed(self) -> "ExitPlan":
        """Return a committed copy of this plan."""
        return replace(self, status=ExitPlanStatus.COMMITTED)


def _format_exit_amount(amount: float, currency: str | None = None) -> str:
    """Format a currency amount for participant-facing exit copy."""
    if currency is None:
        currency = get_config().get("currency", "$")
    return f"{currency}{float(amount):.2f}"


def _format_planned_payment_amount(plan: ExitPlan, name: str) -> str:
    """Format one amount from an exit plan's payment decision."""
    if plan.payment is None:
        raise ValueError("This exit plan has no payment decision.")
    return _format_exit_amount(getattr(plan.payment, name), plan.currency)


def _committed_exit_plan(participant) -> ExitPlan | None:
    """Return the participant's committed exit plan, if present."""
    data = getattr(participant, "exit_plan", None)
    if not isinstance(data, dict):
        return None
    try:
        plan = ExitPlan.from_dict(data)
    except (KeyError, TypeError, ValueError):
        return None
    if plan.status is not ExitPlanStatus.COMMITTED:
        return None
    return plan


def _exit_returns_without_payment(participant) -> bool:
    """Return whether the committed plan records an unpaid return."""
    plan = _committed_exit_plan(participant)
    return plan is not None and plan.path is ExitPath.RETURN_WITHOUT_PAYMENT
