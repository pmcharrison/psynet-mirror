import pandas
import importlib_resources   
from flask import render_template_string

from dlgr_utils.misc import get_template
from dlgr_utils import questionnaires

class Question():
    def __init__(self):
        "Do nothing"

class InfoQuestion():
    def __init__(self, info):
        self.type = "info"
        self.info = info

class DropdownQuestion(Question):
    def __init__(self, id, question, values, labels):
        self.type = "dropdown"
        self.id = id
        self.question = question
        self.values = values
        self.labels = labels

def render_questions(questions):
    assert all([isinstance(x, Question) for x in questions])
    html = get_template("questions.html")
    render_template_string(html, questions = questions)

def get_gold_msi():
    file = importlib_resources.open_text(questionnaires, "gold-msi.csv")
    all = pandas.read_csv(file).query("factor_label == 'Musical Training'")
    choice_ids = [str(1 + x) for x in range(7)]
    info = InfoQuestion("Please select the options that best describe your musical background.")
    questions = [DropdownQuestion(
        id = "gmsi-" + str(row["question_number"]),
        question = row["question"],
        values = choice_ids,   
        labels = [row["btn" + i + "_text"] for i in choice_ids]
    ) for index, row in all.iterrows()]
    return [info] + questions

gold_msi = get_gold_msi()

def get_demographics():
    ages = [str(x) for x in range(151)]
    age = DropdownQuestion(
        id = "age",
        question = "What is your age (in years)?",
        values = ages,
        labels = ages
    )
    gender = DropdownQuestion(
        id = "gender",
        question = "What gender do you identify as?",
        values = ["male", "female", "other", "prefer_not"],
        labels = ["Male", "Female", "Other", "Prefer not to say"]
    )
    return [age, gender]

demographics = get_demographics()

perform_in_public = DropdownQuestion(
    id = "perform-in-public",
    question = "Do you perform music in public?",
    values = ["yes", "no"],
    labels = ["Yes", "No"]
)

paid_to_do_music = DropdownQuestion(
    id = "paid-to-do-music",
    question = "Are you paid for doing music? (e.g. playing an instrument, singing, teaching, composing)",
    values = ["yes", "no"],
    labels = ["Yes", "No"]
)
