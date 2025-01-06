import warnings
from functools import cached_property
from typing import List

import requests


class Translator:
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        raise NotImplementedError

    def _get_response(self, url, json_data):
        response = requests.post(url, json=json_data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error: {response.status_code} {response.reason}")


class DeepLTranslator(Translator):
    # TODO - Enable retry logic once we know what kind of exception needs catching
    # @retry(
    #     retry=retry_if_exception_type(NoResultFound),
    #     wait=wait_exponential(multiplier=1, min=3),
    #     stop=stop_after_delay(4)
    # )
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        assert isinstance(texts, list)
        payload = self._make_payload(texts, source_lang, target_lang)
        response = self._get_response("https://api.deepl.com/jsonrpc", payload)
        return self._parse_response(response)

    def _make_payload(self, sentences: List[str], source_lang: str, target_lang: str):
        return {
            "jsonrpc": "2.0",
            "method": "LMT_handle_jobs",
            "params": {
                "tag_handling": "xml",
                "jobs": self._create_jobs(sentences),
                "lang": {
                    "source_lang_computed": source_lang.upper(),
                    "target_lang": target_lang.upper(),
                },
                "priority": 1,
                "commonJobParams": {
                    "mode": "translate",
                    "browserType": 1,
                    "formality": "formal",
                },
            },
        }

    def _create_jobs(self, sentences, num_alternatives=1):
        return [
            {
                "kind": "default",
                "sentences": [
                    {
                        "text": sentence,
                        "id": i,
                        "prefix": "",
                    },
                ],
                "raw_en_context_before": sentences[:i],
                "raw_en_context_after": sentences[i + 1 :],
                "preferred_num_beams": num_alternatives,
            }
            for i, sentence in enumerate(sentences)
        ]

    def _parse_response(self, json_response):
        return [
            translation["beams"][0]["sentences"][0]["text"]
            for translation in json_response["result"]["translations"]
        ]


class MetaTranslator(Translator):
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        from psynet.translation.languages import (
            get_supported_deepl_languages,
            get_supported_gtrans_languages,
        )

        if target_lang in get_supported_deepl_languages():
            DeepLTranslator().translate(texts, target_lang, source_lang)
        elif target_lang in get_supported_gtrans_languages():
            GoogleTranslator().translate(texts, target_lang, source_lang)
        else:
            raise NotImplementedError(
                f"Language {target_lang} is not supported by DeepL and Google Translate. "
                f"DeepL supports {get_supported_deepl_languages()} and Google Translate supports {get_supported_gtrans_languages()}."
            )


class GoogleTranslator(Translator):
    @cached_property
    def _translator(self):
        from googletrans import Translator

        return Translator()

    # TODO - Enable retry logic once we know what kind of exception needs catching
    # @retry(
    #     retry=retry_if_exception_type(NoResultFound),
    #     wait=wait_exponential(multiplier=1, min=3),
    #     stop=stop_after_delay(4)
    # )
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)

            assert isinstance(texts, list)

            from googletrans import Translator

            translator = Translator()
            response = translator.translate(
                texts, dest=target_lang.lower(), src=source_lang.lower()
            )

            return [translation.text for translation in response]
