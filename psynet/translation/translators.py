import json
import os.path
from os.path import expanduser
from typing import List

from psynet.utils import get_config, get_descendent_class_by_name, get_language_dict


class Translator:
    nickname = None

    def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        file_path: str = None,
    ):
        raise NotImplementedError


class CredentialsError(Exception):
    pass


class UnsupportedLanguageError(Exception):
    pass


class InvalidTranslationError(Exception):
    pass


class GoogleTranslator(Translator):
    nickname = "google_translate"

    def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        file_path: str = None,
    ):
        from google.cloud import translate_v3

        config = get_config()
        args = {
            "google_translate_project_id": config.get(
                "google_translate_project_id", None
            ),
            "google_translate_json_path": config.get(
                "google_translate_json_path", None
            ),
        }
        if not all(args.values()):
            error_msg = "Please provide the following credentials in your .dallingerconfig file: "
            for key, value in args.items():
                if not value:
                    error_msg += f"{key}, "
            raise CredentialsError(error_msg)

        client = translate_v3.TranslationServiceClient.from_service_account_json(
            expanduser(args["google_translate_json_path"])
        )
        parent = f"projects/{args['google_translate_project_id']}/locations/global"
        try:
            response = client.translate_text(
                contents=texts,
                target_language_code=target_lang,
                parent=parent,
                mime_type="text/html",
                source_language_code=source_lang,
            )
        except Exception as e:
            if e.args[0] == "Target language is invalid.":
                raise UnsupportedLanguageError(f"Invalid language code: {target_lang}")
            else:
                raise e

        # Display the translation for each input text provided
        return [translation.translated_text for translation in response.translations]


class ChatGptTranslator(Translator):
    nickname = "chat_gpt"

    def get_system_prompt(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        file_path: str = None,
    ):
        prompt = f"You are a helpful assistant that translates {source_language} to {target_language}."
        prompt += (
            "If you see any HTML tags in the text, you should not translate them. "
            "If you see any variables in the text, you should not translate them. "
            """Variables are written in capital letters and are either surrounded by curly brackets (e.g., {VARIABLE}) or start with "%(" and end with ")s" (e.g., "%(VARIABLE)s"). """
            "You do not have to keep the original word order. "
            "The translation is specified as a list using JSON format. "
            """For example, ["Hello, {NAME}!", "My name is {NAME}"] would be converted to ["Bonjour, {NAME}!", "Je m'appelle {NAME}"] when translating to French. """
        )

        if file_path is not None and os.path.exists(file_path):
            with open(file_path, "r") as f:
                prompt += (
                    f"\n\nThe translations are taken from {file_path}:\n\n{f.read()}"
                )

        return prompt

    def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        file_path: str = None,
    ):
        from openai import OpenAI

        language_dict = get_language_dict("en")
        assert (
            source_lang in language_dict
        ), f"Source language {source_lang} not found in known languages"
        source_language = language_dict[source_lang]
        assert (
            target_lang in language_dict
        ), f"Target language {target_lang} not found in known languages"
        target_language = language_dict[target_lang]

        config = get_config()
        openai_api_key = config.get("openai_api_key", None)
        if openai_api_key is None:
            raise CredentialsError(
                "Please provide an OpenAI API key in your .dallingerconfig file under `openai_api_key`"
            )
        temperature = float(config.get("openai_default_temperature"))
        openai_default_model = config.get("openai_default_model")

        client = OpenAI(api_key=openai_api_key)
        messages = [
            {
                "role": "system",
                "content": self.get_system_prompt(
                    texts, source_language, target_language, file_path
                ),
            },
            {"role": "user", "content": json.dumps(texts)},
        ]
        response = client.chat.completions.create(
            model=openai_default_model,
            messages=messages,
            temperature=temperature,
        )
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            InvalidTranslationError(
                f"Invalid translation: {response.choices[0].message.content}"
            )


class DefaultTranslator(Translator):
    def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        file_path: str = None,
    ):
        from psynet.experiment import import_local_experiment

        config = get_config()
        default_translator = config.get("default_translator")
        import_local_experiment()
        translator_class = get_descendent_class_by_name(Translator, default_translator)
        return translator_class().translate(texts, source_lang, target_lang, file_path)
