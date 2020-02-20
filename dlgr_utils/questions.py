import pandas
import importlib_resources   
import json

from operator import attrgetter
from flask import render_template_string

from dallinger.models import Participant

from . import page
from . import definitions

class Question():
    def __init__(self):
        "Do nothing"

class InfoQuestion(Question):
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

def render_questions(questions, name = "final", next_page = ""):
    assert all([isinstance(x, Question) for x in questions])
    assert isinstance(name, str)
    assert isinstance(next_page, str)

    html = page.get_template("questions.html")
    return render_template_string(html, questions = questions, name = name, next_page = next_page)

def get_gold_msi():
    file = importlib_resources.open_text(definitions, "gold-msi.csv")
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

def first(x):
    return x[0]

def last(x):
    return x[len(x) - 1]

def get_questionnaire_response(participant_id, questionnaire, field = None, which = "first", must_work = True):
    assert isinstance(questionnaire, str)
    assert field is None or isinstance(field, str)
    assert isinstance(must_work, bool)
    assert which in ["first", "last"]

    participant = Participant.query.get(participant_id)
    all_submissions = participant.questions()
    relevant_submissions = [x for x in all_submissions if x.question == questionnaire]
    relevant_submissions.sort(key = attrgetter("creation_time"))

    if len(relevant_submissions) == 0:
        if must_work:
            raise Exception("No questionnaire submissions found with name '{}' for participant_id {}.".format(questionnaire, participant_id))
        else:
            return None

    chosen = first(relevant_submissions) if which == "first" else last(relevant_submissions)
    responses = json.loads(chosen.response)

    if field is None:
        return responses
    else:
        return responses[field]
   