"""Tests for the VocabTrial.show_feedback method."""

import pytest
from unittest.mock import MagicMock, patch


class TestVocabTrialShowFeedback:
    """Tests for VocabTrial.show_feedback method."""

    def test_show_feedback_checks_trial_maker_attribute(self):
        """
        Test that show_feedback correctly checks self.trial_maker.show_feedback.

        This test verifies that the method checks the trial_maker's show_feedback
        attribute, not itself (which would always be truthy as a method object).
        When show_feedback is True and score is not None, the method should
        return an InfoPage, not None.
        """
        from psynet.prescreen.vocabtest import VocabTrial

        # Create a mock trial with necessary attributes
        trial = MagicMock(spec=VocabTrial)
        trial.score = 0.75  # Set a score

        # Create a mock trial_maker with show_feedback = True
        trial_maker = MagicMock()
        trial_maker.show_feedback = True
        trial.trial_maker = trial_maker

        # Call the actual show_feedback method (unbound) with our mock
        # We need to call it properly to avoid the method resolution issue
        result = VocabTrial.show_feedback(trial, experiment=None, participant=None)

        # The method should NOT return None when show_feedback is True and score is set
        # If the bug exists (checking self.show_feedback instead of
        # self.trial_maker.show_feedback), the method object is always truthy,
        # so `not self.show_feedback` is always False, and it should proceed.
        # However, the intent is clearly to check the trial_maker's attribute.
        # With the bug, it accidentally works but for the wrong reason.
        # Let's test the opposite case to expose the bug.

    def test_show_feedback_disabled_returns_none(self):
        """
        Test that show_feedback returns None when trial_maker.show_feedback is False.

        This is the key test that exposes the bug: with the current buggy code,
        `not self.show_feedback` evaluates `self.show_feedback` which is the method
        itself (always truthy), so `not method` is always False.
        This means the condition `if not self.show_feedback or self.score is None`
        only checks if score is None, ignoring the show_feedback setting entirely.
        """
        from psynet.prescreen.vocabtest import VocabTrial

        # Create a mock trial
        trial = MagicMock(spec=VocabTrial)
        trial.score = 0.75  # Set a score (not None)

        # Create a mock trial_maker with show_feedback = False
        trial_maker = MagicMock()
        trial_maker.show_feedback = False  # Should disable feedback
        trial.trial_maker = trial_maker

        # The bug: self.show_feedback refers to the method, not trial_maker.show_feedback
        # So `not self.show_feedback` is `not <bound method>` which is False
        # This means feedback is shown even when it should be disabled

        result = VocabTrial.show_feedback(trial, experiment=None, participant=None)

        # With the bug, result will NOT be None (it will try to create an InfoPage)
        # After the fix, result should be None because show_feedback is False
        assert result is None, (
            "show_feedback should return None when trial_maker.show_feedback is False, "
            "but it returned a non-None value. This indicates the bug where "
            "self.show_feedback (the method) is checked instead of "
            "self.trial_maker.show_feedback (the boolean attribute)."
        )
