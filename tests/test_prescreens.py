import pytest

from psynet.bot import Bot


@pytest.mark.usefixtures("demo_color_blindness")
class TestColorBlindness:
    def test_exp(self, active_config, debug_experiment):
        bot = Bot()
        bot.take_experiment()


@pytest.mark.usefixtures("demo_color_vocabulary")
class TestColorVocabulary:
    def test_exp(self, active_config, debug_experiment):
        bot = Bot()
        bot.take_experiment()


@pytest.mark.usefixtures("demo_headphone_test")
class TestHeadphoneTest:
    def test_exp(self, active_config, debug_experiment):
        bot = Bot()
        bot.take_experiment()


@pytest.mark.usefixtures("demo_language_tests")
class TestLanguageTests:
    def test_exp(self, active_config, debug_experiment):
        bot = Bot()
        bot.take_experiment()
