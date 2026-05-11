Recruiter-Specific Deployment Steps
===================================

Prolific
--------


CINT Qualifications
^^^^^^^^^^^^^^^^^^^

Setting Qualifications Automatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CINT has a standard qualification library and you can create custom
qualifications.

Currently, we have the following custom qualifications:

-  [\`\ `TIMEOUT <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=187e22aa-8a67-45c9-8a7c-481eeeaddfb0>`__\ \`]:
   warning participants they can't leave the page as they might be
   kicked out otherwise (set automatically)

-  [\`\ `MONOLINGUALISM <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=08a162fe-4c14-48c7-b850-1d09f95527a1>`__\ \`]:
   asking participants if they are monolingual

-  [\`\ `HAS_AUDIO <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=25434891-030a-405a-9616-e43961d674fa>`__\ \`]:
   asking participants if they can play audio

-  [\`\ `ALLOW_VOICE_RECORDING <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=9242d802-f6d6-4786-8049-50490dcd5179>`__\ \`]:
   asking participants if they can record their voice

-  [\`\ `BORN_IN_COUNTRY <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=2a6d41c7-c38c-4a69-ad12-2cca5074d98f>`__\ \`]:
   asking participants if they were born in the country

-  [\`\ `HAS_NATIONALITY <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=f91c6b4f-7167-4e30-95ab-9efb408f0537>`__\ \`]:
   asking participants

-  [\`\ `IS_NATIVE <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=c0833d98-be26-46df-8e01-1abbb740cda6>`__\ \`]:
   asking participants if they are native speakers

There are a variety of languages and countries available on CINT with
specific tags. You can get a list of all the available language (3
capital letters) and country (2 capital letters) tags by running the
following code in your terminal:

.. code:: bash

   psynet lucid locale

After getting the desired locales, you can generate qualifications
specific to each country by using a custom create_qualifications.py.
Please find an example code below that you can adjust and add to your
create_qualifications.py.

.. code:: python

   from tqdm import tqdm
   from psynet.lucid.qualifications import create_lucid_recruitment_config

   country_language_tags = (("DUT", "NL"),)

   for language_tag, country_tag in tqdm(country_language_tags):
       config_path = f"qualifications/lucid/lucid-{language_tag}-{country_tag}.json"
       create_lucid_recruitment_config(
           language_tag=language_tag,
           country_tag=country_tag,
           question_answer_dict={
               "MONOLINGUALISM": ["I was raised with my native language only"],
               "HAS_AUDIO": ["Yes"],
               "ALLOW_VOICE_RECORDING": ["Yes"],
               "BORN_IN_COUNTRY": ["Yes"],
               "HAS_NATIONALITY": ["Yes"],
               "IS_NATIVE": ["Yes"],
           },
           config_path=config_path,
           debug=True,
       )

Extending the qualification to new languages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can expand an existing qualification for a new language. Go to the
qualification page and add the question and the options. Make sure that
the options are in the same order as in the original. It is recommended
to use the English language as a reference so that the options match up.

Adding a new qualification
~~~~~~~~~~~~~~~~~~~~~~~~~~

Go to the [`qualification overview
page <https://www.samplicio.us/fulcrum/Questions.aspx>`__] and click the
button "Add Qualification". Now set the Qualification Name. It is
recommended to use only capital letters and underscores
(e.g.`HAS_AUDIO\`). For the Qualification Type, select "Conditional List
– Single Punch". Set Minimum Displayed Conditions and Maximum Displayed
Conditions to 2. Now click "Save". Move down to "Step 2: Questions".
Click "Add Question Text". Select the language country pair you want to
add. Add the question text. Now add the options with line breaks in
"Mass Upload" and select the right language pair. Click "Save".

It takes some time for CINT to register new custom qualifications. If
you want to use it in your experiment, go to your qualification page,
right-click in Chrome on the page, and select "View Page Source". Now
search for "QuestionID", this field is the ID of the qualification. You
can now use this ID in your experiment:

.. code:: python

   from psynet.experiment import get_and_load_config
   from psynet.lucid import get_lucid_service
   from psynet.lucid.qualifications import create_lucid_recruitment_config

   language_tag = "DUT"
   country_tag = "NL"
   config_path = f"qualifications/lucid/lucid-{language_tag}-{country_tag}.json"

   config = get_and_load_config()
   service = get_lucid_service(config=config)
   custom_qualifications_dict = {
       **service.get_qualifications_dict(),
       "MY_NEW_QUALIFICATION": 200093,  # replace 200093 with actual ID
   }

   create_lucid_recruitment_config(
       language_tag=language_tag,
       country_tag=country_tag,
       question_answer_dict={
           "MONOLINGUALISM": ["I was raised with my native language only"],
           "HAS_AUDIO": ["Yes"],
           "ALLOW_VOICE_RECORDING": ["Yes"],
           "BORN_IN_COUNTRY": ["Yes"],
           "HAS_NATIONALITY": ["Yes"],
           "IS_NATIVE": ["Yes"],
       },
       config_path=config_path,
       debug=True,
       config=config,
       service=service,
       qualifications_dict=custom_qualifications_dict,
   )

Front-end confirmation of qualifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is recommended to let users confirm the qualifications in the
front-end. There are multiple reasons for this:

-  First, on the qualification pages, we have strict rules concerning
   how long they can leave the page. Since the majority of participants
   leave the experiment on the first page, this is a good way to
   terminate them here. Also, since this is fairly fast, it will reduce
   the termination LOI.

-  Second, it is good to double-check the requirements.

To do this, you can use the following code:

.. code:: python

   import psynet.experiment
   from psynet.consent import LucidConsent
   from psynet.timeline import Timeline
   from psynet.page import SuccessfulEndPage
   from psynet.lucid.qualifications import verify_lucid_qualifications

   LANGUAGE = "DUT"
   COUNTRY = "NL"
   LUCID_CONFIG_PATH = f"qualifications/lucid/lucid-{LANGUAGE}-{COUNTRY}.json"

   class Exp(psynet.experiment.Experiment):
       timeline = Timeline(
           verify_lucid_qualifications(LUCID_CONFIG_PATH),
           LucidConsent(),
           SuccessfulEndPage(),
       )

If you don't want to show all qualifications to the participants or want
to show them in a different order, you can specify them as an additional
argument:

.. code:: python

   verify_lucid_qualifications(
       LUCID_CONFIG_PATH,
       question_names=["TIMEOUT", "MONOLINGUALISM"],
   )

Summary Steps for Setting CINT Qualifications:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1) Access a list of available language and country tags using the
   command psynet lucid locale.

2) Use the provided Python script to create predefined qualifications
   (e.g.`HAS_AUDIO\`) specific to each country.

3) Be sure that you have added the following parameters to your
   experiment.py:

.. code:: python

   LANGUAGE = "DUT"  # lucid language code, not ISO language code
   COUNTRY = "NL"  # lucid country code, not always ISO country code
   LOCALE = "nl"  # ISO-2 code for experiment language
   LUCID_CONFIG_PATH = f"qualifications/lucid/lucid-{LANGUAGE}-{COUNTRY}.json"

4) Implement front-end confirmation of qualifications to ensure
   participant adherence to requirements and improve termination
   efficiency. Optionally, you can specify which qualifications to
   display and their order using additional arguments in the front-end
   confirmation code. Adjust and add the following code to your
   timeline.

.. code:: python

   verify_lucid_qualifications(
       LUCID_CONFIG_PATH,
       question_names=["TIMEOUT", "MONOLINGUALISM"],
   )



