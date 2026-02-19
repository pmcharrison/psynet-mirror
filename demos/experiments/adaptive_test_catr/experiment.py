"""
Adaptive Testing with catR via rpy2

This demo shows how to use the catR R package for computerized adaptive testing (CAT)
in a PsyNet experiment. It uses rpy2 to interface between Python and R.

The catR package provides various item selection methods, ability estimation procedures,
and stopping rules for adaptive testing. This example demonstrates a simple ability
estimation scenario.
"""

import random

from dominate import tags

import psynet.experiment
from psynet.bot import Bot
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage
from psynet.timeline import Timeline
from psynet.trial import Trial
from psynet.trial.main import TrialMaker

# Import rpy2 for interfacing with R
try:
    import rpy2.robjects as robjects
    from rpy2.robjects.packages import importr

    # Import the catR package
    catr = importr("catR")
    R_AVAILABLE = True
except Exception as e:
    print(f"Warning: R/catR not available: {e}")
    R_AVAILABLE = False


# Example item bank for demonstration purposes
# In a real CAT, you would have a calibrated item bank with difficulty parameters
# Format: [difficulty, discrimination, guessing, inattention]
ITEM_BANK = [
    [-2.0, 1.0, 0.0, 1.0],  # Easy item
    [-1.0, 1.2, 0.0, 1.0],
    [0.0, 1.1, 0.0, 1.0],  # Medium difficulty
    [1.0, 1.3, 0.0, 1.0],
    [2.0, 1.0, 0.0, 1.0],  # Hard item
]


def estimate_ability_with_catr(responses, item_params):
    """
    Estimate participant ability using catR's maximum likelihood estimation.

    Args:
        responses: List of binary responses (1 for correct, 0 for incorrect)
        item_params: List of item parameters used

    Returns:
        Estimated ability (theta) value
    """
    if not R_AVAILABLE:
        # Fallback: simple proportion correct
        return sum(responses) / len(responses) if responses else 0.0

    try:
        # Convert Python data to R vectors
        r_responses = robjects.IntVector(responses)
        r_item_bank = robjects.r.matrix(
            robjects.FloatVector([param for item in item_params for param in item]),
            nrow=len(item_params),
            ncol=4,
            byrow=True,
        )

        # Use catR's thetaEst function for maximum likelihood estimation
        # method="ML" uses Maximum Likelihood Estimation
        result = catr.thetaEst(r_item_bank, r_responses, method="ML")

        # Extract the theta estimate
        theta = result[0][0]
        return float(theta)

    except Exception as e:
        print(f"Error in catR ability estimation: {e}")
        # Fallback to simple proportion correct
        return sum(responses) / len(responses) if responses else 0.0


def select_next_item_with_catr(current_theta, already_used_items):
    """
    Select the next item using catR's maximum information criterion.

    Args:
        current_theta: Current ability estimate
        already_used_items: List of item indices already administered

    Returns:
        Index of the next item to administer
    """
    if not R_AVAILABLE:
        # Fallback: random selection from unused items
        available = [i for i in range(len(ITEM_BANK)) if i not in already_used_items]
        return random.choice(available) if available else 0

    try:
        # Create R matrix of available items
        available_indices = [
            i for i in range(len(ITEM_BANK)) if i not in already_used_items
        ]
        if not available_indices:
            return 0

        available_items = [ITEM_BANK[i] for i in available_indices]
        r_item_bank = robjects.r.matrix(
            robjects.FloatVector([param for item in available_items for param in item]),
            nrow=len(available_items),
            ncol=4,
            byrow=True,
        )

        # Use catR's nextItem function with maximum Fisher information criterion
        result = catr.nextItem(
            itemBank=r_item_bank, theta=current_theta, criterion="MFI"
        )

        # Get the selected item index (R uses 1-based indexing)
        selected_idx = int(result[0]) - 1
        return available_indices[selected_idx]

    except Exception as e:
        print(f"Error in catR item selection: {e}")
        # Fallback to random selection
        available = [i for i in range(len(ITEM_BANK)) if i not in already_used_items]
        return random.choice(available) if available else 0


class AdaptiveTestTrial(Trial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        # Get participant's response history
        previous_trials = participant.trials.filter_by(
            trial_maker_id=self.trial_maker_id
        ).all()

        # Determine which item to present
        if not previous_trials:
            # First trial: start with medium difficulty
            item_idx = 2
        else:
            # Extract responses and item parameters from previous trials
            responses = [t.answer["correct"] for t in previous_trials]
            item_indices = [t.var.item_idx for t in previous_trials]
            item_params = [ITEM_BANK[i] for i in item_indices]

            # Estimate current ability
            current_theta = estimate_ability_with_catr(responses, item_params)

            # Select next item
            item_idx = select_next_item_with_catr(current_theta, item_indices)

        # Store item index for later use
        self.var.item_idx = item_idx
        item_difficulty = ITEM_BANK[item_idx][0]

        # Create a simple question based on item difficulty
        # In a real experiment, you would retrieve actual test items
        question = f"Question {len(previous_trials) + 1}: Is 2 + 2 equal to 4?"
        if item_difficulty < -1:
            question = "Very easy question: Is 1 + 1 equal to 2?"
        elif item_difficulty < 0:
            question = "Easy question: Is 3 + 2 equal to 5?"
        elif item_difficulty < 1:
            question = "Medium question: Is 7 + 8 equal to 15?"
        else:
            question = "Hard question: Is 13 + 17 equal to 30?"

        return ModularPage(
            "adaptive_test",
            tags.p(question),
            tags.p(
                f"(Item difficulty: {item_difficulty:.2f}, "
                f"Trial {len(previous_trials) + 1} of {experiment.timeline.n_trials})"
            ),
            PushButtonControl(
                choices=["True", "False"],
                arrange_vertically=False,
            ),
        )

    def process_answer(self, answer, experiment, participant):
        # Determine if answer is correct
        # In this simple example, all questions have "True" as the correct answer
        correct = answer == "True"

        return {"correct": 1 if correct else 0, "response": answer}


class AdaptiveTestTrialMaker(TrialMaker):
    performance_check_type = None
    give_end_feedback_passed = False

    def make_trials(self, participant, experiment):
        # Create 10 adaptive trials
        return [AdaptiveTestTrial() for _ in range(10)]


timeline = Timeline(
    InfoPage(
        """
        # Adaptive Testing Demo with catR

        This experiment demonstrates computerized adaptive testing (CAT) using the catR R package.

        You will answer a series of questions. The difficulty of each question will be adapted
        based on your previous responses using item response theory.

        Click 'Next' to begin.
        """,
        time_estimate=5,
    ),
    AdaptiveTestTrialMaker(),
    InfoPage(
        """
        # Thank you!

        You have completed the adaptive test.

        In a real experiment, your estimated ability would be calculated using
        the catR package's sophisticated psychometric algorithms.
        """,
        time_estimate=3,
    ),
)


class Exp(psynet.experiment.Experiment):
    label = "Adaptive Testing with catR"
    timeline = timeline

    config = {
        "initial_recruitment_size": 1,
    }

    def __init__(self, session=None):
        super().__init__(session)
        # Log R/catR availability
        if R_AVAILABLE:
            print("✓ R and catR are available for adaptive testing")
        else:
            print("⚠ R/catR not available, using fallback methods")


class ExpBot(Bot):
    def answer_trial(self, experiment, trial):
        # Bot randomly answers True or False
        return random.choice(["True", "False"])
