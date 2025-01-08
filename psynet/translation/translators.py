import json
import os.path
from typing import List

from psynet.utils import get_config, get_descendent_class_by_name, get_language_dict


class Translator:
    nickname = None
    use_codebook = True

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
        google_translate_json_path = config.get("google_translate_json_path", None)
        if google_translate_json_path is None:
            raise CredentialsError(
                "Please provide a Google Cloud Translate API key in your .dallingerconfig file under `google_translate_json_path`"
            )

        google_translate_json_path = os.path.expanduser(google_translate_json_path)

        with open(google_translate_json_path, "r") as f:
            auth_dict = json.load(f)

        client = translate_v3.TranslationServiceClient.from_service_account_json(
            google_translate_json_path
        )
        parent = f"projects/{auth_dict['project_id']}/locations/global"
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
    use_codebook = False

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
            "Your output should be pure JSON with no comments, formatting directives, or other modifiers"
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
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise InvalidTranslationError(
                f"ChatGPT did not return a proper JSON string: {content}"
            ) from e


class DefaultTranslator(Translator):
    def translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        file_path: str = None,
    ):
        config = get_config()
        default_translator = config.get("default_translator")
        translator_class = get_descendent_class_by_name(Translator, default_translator)
        return translator_class().translate(texts, source_lang, target_lang, file_path)
