# TODO remove dependency on googletrans
# TODO add developer dependency google-cloud-translate==2.0.1
import configparser

# Steps:
# Add a project, copy the project ID and store it to `google_translate_project_id` in .dallingerconfig
# Enable the Cloud Translation API
# Create a service account
# Go to the keys tab and create a new key as JSON and store it to your computer, store the path to `google_translate_json_path` in .dallingerconfig
import os

from google.cloud import translate_v3

config = configparser.ConfigParser()
config.read(os.path.expanduser("~/.dallingerconfig"))
PROJECT_ID = config.get("Google Translate", "google_translate_project_id")
KEY_JSON = os.path.expanduser(
    config.get("Google Translate", "google_translate_json_path")
)


# Initialize Translation client
def translate_text(
    text: str = "YOUR_TEXT_TO_TRANSLATE",
    language_code: str = "fr",
) -> translate_v3.TranslationServiceClient:
    """Translating Text from English.
    Args:
        text: The content to translate.
        language_code: The language code for the translation.
            E.g. "fr" for French, "es" for Spanish, etc.
            Available languages: https://cloud.google.com/translate/docs/languages#neural_machine_translation_model
    """

    client = translate_v3.TranslationServiceClient.from_service_account_json(KEY_JSON)
    parent = f"projects/{PROJECT_ID}/locations/global"
    # Translate text from English to chosen language
    # Supported mime types: # https://cloud.google.com/translate/docs/supported-formats
    response = client.translate_text(
        contents=[text],
        target_language_code=language_code,
        parent=parent,
        mime_type="text/plain",
        source_language_code="en-US",
    )

    # Display the translation for each input text provided
    for translation in response.translations:
        print(f"Translated text: {translation.translated_text}")
    # Example response:
    # Translated text: Bonjour comment vas-tu aujourd'hui?

    return response


translate_text("You sexy thing")
