import configparser

# Steps:
# Setup an OpenAI account with billing and create an API key
# Put the API key in `openai_api_key` in .dallingerconfig
import os

from openai import OpenAI

from psynet.translation.languages import get_known_languages

config = configparser.ConfigParser()
config.read(os.path.expanduser("~/.dallingerconfig"))
MODEL = config.get("OpenAI", "openai_default_model")
TEMPERATURE = float(config.get("OpenAI", "openai_default_temperature"))
target = "de"

client = OpenAI(api_key=config.get("OpenAI", "openai_api_key"))


def translate(text, target_language):
    # TODO maybe move this to experiment.py for overriding
    message = (
        f"You are a helpful assistant that translates English to {target_language}."
        + """
            If you see any HTML tags in the text, you should not translate them.
            If you see any variables in the text, you should not translate them.
            Variables are written in capital letters and are either surrounded by curly brackets (e.g., {VARIABLE}) or start with "%(" and end with ")s" (e.g., "%(VARIABLE)s").
            You do not have to keep the original word order.
            """
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": message},
            {"role": "user", "content": text},
        ],
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content


language_pairs = get_known_languages()
language_dict = {pair[0]: pair[1] for pair in language_pairs}
assert target in language_dict, f"Target language {target} not found in known languages"
target_language = language_dict[target]
translate(
    "<strong>THIS</strong> IS NOT A VARIABLE, but this is a {NAME} and this is a {AGE}",
    target_language,
)
