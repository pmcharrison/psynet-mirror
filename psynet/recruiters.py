import json
import os

import dallinger.recruiters
import flask
import requests
from dallinger.config import get_config
from dallinger.db import session
from dallinger.heroku import tools as heroku_tools
from dallinger.notifications import admin_notifier, get_mailer
from dallinger.recruiters import RedisStore
from dallinger.utils import get_base_url

from .lucid import LucidService, LucidServiceException
from .utils import get_logger

logger = get_logger()


class BaseCapRecruiter(dallinger.recruiters.CLIRecruiter):

    """
    The CapRecruiter base class

    """

    def open_recruitment(self, n=1):
        """
        Return an empty list which otherwise would be a list of recruitment URLs.
        """
        return {"items": [], "message": ""}

    def recruit(self, n=1):
        return []

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

    def compensate_worker(self, *args, **kwargs):
        """A recruiter may provide a means to directly compensate a worker."""
        raise RuntimeError("Compensation is not implemented.")

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            session.commit()

    def reward_bonus(self, assignment_id, amount, reason):
        """
        Return values for `basePay` and `bonus` to cap-recruiter application.
        """
        data = {
            "assignmentId": assignment_id,
            "basePayment": self.config.get("base_payment"),
            "bonus": amount,
        }
        requests.post(
            self.external_submission_url,
            json=data,
            headers={"Authorization": os.environ.get("CAP_RECRUITER_AUTH_TOKEN")},
            verify=False,  # Temporary fix because of SSLCertVerificationError
        )


class CapRecruiter(BaseCapRecruiter):

    """
    The production cap-recruiter.

    """

    nickname = "cap-recruiter"
    external_submission_url = "https://cap-recruiter.ae.mpg.de/hits/complete"


class StagingCapRecruiter(BaseCapRecruiter):

    """
    The staging cap-recruiter.

    """

    nickname = "staging-cap-recruiter"
    external_submission_url = "https://staging-cap-recruiter.ae.mpg.de/hits/complete"


class DevCapRecruiter(BaseCapRecruiter):

    """
    The development cap-recruiter.

    """

    nickname = "dev-cap-recruiter"
    external_submission_url = "http://localhost:8000/hits/complete"


class LucidRecruiterException(Exception):
    """Custom exception for LucidRecruiter"""


class BaseLucidRecruiter(dallinger.recruiters.CLIRecruiter):
    """
    The LucidRecruiter base class
    """

    external_submission_url = ""
    # extra_routes = mturk_routes

    def __init__(self, *args, **kwargs):
        super(BaseLucidRecruiter, self).__init__()
        self.config = get_config()
        self.ad_url = f"{self.base_url}/ad?recruiter={self.nickname}"
        self.notifies_admin = admin_notifier(self.config)
        self.mailer = get_mailer(self.config)
        self.store = kwargs.get("store") or RedisStore()
        self.survey_domain = os.getenv("HOST")
        self.lucidservice = LucidService(
            api_key=self.config.get("lucid_api_key"),
            sandbox=self.config.get("mode") != "live",
            recruitment_config=json.loads(self.config.get("lucid_recruitment_config")),
        )
        self.external_submission_url = self.survey_update_url
        # self._validate_config()

    @property
    def survey_update_url(self):
        """
        On experiment completion, participants are returned to
        the Lucid Marketplace site to submit their survey.
        """
        return self.lucidservice.survey_update_url

    @property
    def is_in_progress(self):
        """Does an Lucid survey for the current experiment ID already exist?"""
        return self.current_survey_id() is not None

    @property
    def survey_id_storage_key(self):
        experiment_id = self.config.get("id")
        return "{}:{}".format(self.__class__.__name__, experiment_id)

    @property
    def quota_id_storage_key(self):
        experiment_id = self.config.get("id")
        return "{}:{}:QUOTA".format(self.__class__.__name__, experiment_id)

    def current_survey_id(self):
        """
        Return the ID of the survey associated with the active experiment ID
        if any such survey exists.
        """
        return self.store.get(self.survey_id_storage_key)

    def _record_current_survey_id(self, survey_id):
        self.store.set(self.survey_id_storage_key, survey_id)

    def current_quota_id(self):
        """
        Return the ID of the quota associated with the active experiment ID
        if any such quota exists.
        """
        return self.store.get(self.quota_id_storage_key)

    def _record_current_quota_id(self, quota_id):
        self.store.set(self.quota_id_storage_key, quota_id)

    def open_recruitment(self, n=1):
        """Open a connection to Lucid and create a survey."""
        logger.info(
            "OPEN RECRUITMENT: OPENING INITIAL RECUITMENT FOR {n} PARTICIPANTS."
        )
        if self.is_in_progress:
            raise LucidRecruiterException(
                "Tried to open_recruitment on already open recruiter."
            )

        # if self.survey_domain is None:
        #     raise LucidRecruiterException("Can't run a survey from localhost")

        create_survey_request_params = {
            "id": heroku_tools.app_name(self.config.get("id")),
            "name": self.config.get("title"),
            "live_url": self.ad_url,
        }

        survey_info = self.lucidservice.create_survey(**create_survey_request_params)
        self._record_current_survey_id(survey_info["id"])
        url = survey_info["live_url"]
        logger.info("OPEN RECRUITMENT: DONE CREATING PROJECT AND SURVEY.")

        # Recruit
        logger.info("OPEN RECRUITMENT: CREATING QUALIFICATIONS AND QUOTA.")

        if not self.config.get("auto_recruit"):
            logger.info("auto_recruit is False: recruitment suppressed.")
            return

        survey_id = self.current_survey_id()
        if survey_id is None:
            logger.info("No survey in progress: recruitment aborted.")
            return

        try:
            qualifications_and_quota_info = (
                self.lucidservice.create_qualifications_and_quota(
                    survey_id,
                    number=n,
                    duration_hours=self.config.get("duration"),
                )
            )
            self._record_current_quota_id(
                qualifications_and_quota_info["Quotas"][1]["SurveyQuotaID"]
            )
            logger.info(f"OPEN RECRUITMENT: QUOTA ID IS: {self.current_quota_id()}")
        except LucidServiceException as e:
            logger.exception(str(e))

        logger.info("OPEN RECRUITMENT: SURVEY PUBLISHED TO LUCID MARKETPLACE.")

        return {
            "items": [url],
            "message": "Survey published to Lucid Marketplace.",
        }

    def recruit(self, n=1):
        logger.info(
            f"RECRUIT: RECRUITING ANOTHER {n} PARTICIPANTS ------------------------------."
        )
        response_data = None

        try:
            quotas = self.lucidservice.get_quotas(self.current_survey_id())
            n = quotas["Quotas"][1]["Quota"] + n
            response_data = self.lucidservice.update_quota(
                self.current_survey_id(), self.current_quota_id(), number=n
            )
        except LucidServiceException as e:
            logger.exception(str(e))

        logger.info(response_data)
        logger.info(
            f"RECRUIT: QUOTA WITH ID '{self.current_quota_id()}'' UPDATED TO {n}. --------"
        )

        return response_data

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

    def compensate_worker(self, *args, **kwargs):
        """A recruiter may provide a means to directly compensate a worker."""
        raise RuntimeError("Compensation is not implemented.")

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            session.commit()

    def exit_response(self, experiment, participant):
        """
        Delegate to the experiment for possible values to show to the
        participant and complete the survey if no more participants are needed.
        """
        if not experiment.need_more_participants:
            response_data = self.lucidservice.complete_survey(self.current_survey_id())
            logger.info(f"'Complete survey' request returned: {response_data}")

        exit_info = sorted(experiment.exit_info_for(participant).items())
        return flask.render_template(
            "exit_recruiter.html",
            recruiter=self.__class__.__name__,
            participant_exit_info=exit_info,
        )


class DevLucidRecruiter(BaseLucidRecruiter):
    """
    The development Lucid recruiter.
    Recruit sandbox participants from Lucid Marketplace
    """

    nickname = "dev-lucid-recruiter"

    def __init__(self, *args, **kwargs):
        self.base_url = "https://localhost:5000"
        super(DevLucidRecruiter, self).__init__()


class StagingLucidRecruiter(BaseLucidRecruiter):
    """
    The staging Lucid recruiter.
    Recruit sandbox participants from Lucid Marketplace
    """

    nickname = "staging-lucid-recruiter"

    def __init__(self, *args, **kwargs):
        self.base_url = get_base_url() + "&generate_tokens=1"
        super(StagingLucidRecruiter, self).__init__()

    # def _validate_config(self):
    #     mode = self.config.get("mode")
    #     if mode not in ("sandbox", "live"):
    #         raise LucidRecruiterException(
    #             '"{}" is not a valid mode for Lucid recruitment. '
    #             'The value of "mode" must be either "sandbox" or "live"'.format(mode)
    #         )

    # @property
    # def external_submission_url(self):
    #     """On experiment completion, participants are returned to
    #     the Mechanical Turk site to submit their HIT, which in turn triggers
    #     notifications to the /mturk-sns-listener route.
    #     """
    #     if self.is_sandbox:
    #         return "https://workersandbox.mturk.com/mturk/externalSubmit"
    #     return "https://www.mturk.com/mturk/externalSubmit"

    # def assign_experiment_qualifications(self, worker_id, qualifications):
    #     """Assigns MTurk Qualifications to a worker.

    #     This can be slow, and the call originates with a web request to the
    #     /worker_complete route, which we don't want to time out.
    #     Since we don't need to return a value, we can offload the work to
    #     an async worker.

    #     @param worker_id       string  the MTurk worker ID
    #     @param qualifications  list of dict w/   `name`, `description` and
    #                            (optional) `score` keys
    #     """
    #     q = _get_queue()
    #     q.enqueue(_run_mturk_qualification_assignment, worker_id, qualifications)

    # def _assign_experiment_qualifications(self, worker_id, qualifications):
    #     # Called from an async worker.
    #     by_name = {qual["name"]: qual for qual in qualifications}
    #     result = self._ensure_mturk_qualifications(qualifications)
    #     for qual in result["new_qualifications"]:
    #         score = by_name[qual["name"]].get("score")
    #         if score is not None:
    #             self.mturkservice.assign_qualification(
    #                 qual["id"], worker_id, qual["score"]
    #             )
    #         else:
    #             self.mturkservice.increment_qualification_score(qual["id"], worker_id)
    #     for name in result["existing_qualifications"]:
    #         score = by_name[name].get("score")
    #         if score is not None:
    #             self.mturkservice.assign_named_qualification(name, worker_id, score)
    #         else:
    #             self.mturkservice.increment_named_qualification_score(name, worker_id)

    # def compensate_worker(self, worker_id, email, dollars, notify=True):
    #     """Pay a worker by means of a special HIT that only they can see."""
    #     qualification = self.mturkservice.create_qualification_type(
    #         name="Dallinger Compensation Qualification - {}".format(
    #             generate_random_id()
    #         ),
    #         description=(
    #             "You have received a qualification to allow you to complete a "
    #             "compensation HIT from Dallinger for ${}.".format(dollars)
    #         ),
    #     )
    #     qid = qualification["id"]
    #     self.mturkservice.assign_qualification(qid, worker_id, 1, notify=notify)
    #     hit_request = {
    #         "experiment_id": "(compensation only)",
    #         "max_assignments": 1,
    #         "title": "Dallinger Compensation HIT",
    #         "description": "For compenation only; no task required.",
    #         "keywords": [],
    #         "reward": float(dollars),
    #         "duration_hours": 1,
    #         "lifetime_days": 3,
    #         "question": MTurkQuestions.compensation(sandbox=self.is_sandbox),
    #         "qualifications": [MTurkQualificationRequirements.must_have(qid)],
    #         "do_subscribe": False,
    #     }
    #     hit_info = self.mturkservice.create_hit(**hit_request)
    #     if email is not None:
    #         message = {
    #             "subject": "Dallinger Compensation HIT",
    #             "sender": self.config.get("dallinger_email_address"),
    #             "recipients": [email],
    #             "body": (
    #                 "A special compensation HIT is available for you to complete on MTurk.\n\n"
    #                 "Title: {title}\n"
    #                 "Reward: ${reward:.2f}\n"
    #                 "URL: {worker_url}"
    #             ).format(**hit_info),
    #         }

    #         self.mailer.send(**message)
    #     else:
    #         message = {}

    #     return {"hit": hit_info, "qualification": qualification, "email": message}

    # def notify_duration_exceeded(self, participants, reference_time):
    #     """The participant has exceed the maximum time for the activity,
    #     defined in the "duration" config value. We need find out the assignment
    #     status on MTurk and act based on this.
    #     """
    #     unsubmitted = []
    #     for participant in participants:
    #         summary = ParticipationTime(participant, reference_time, self.config)
    #         status = self._mturk_status_for(participant)

    #         if status == "Approved":
    #             participant.status = "approved"
    #             session.commit()
    #         elif status == "Rejected":
    #             participant.status = "rejected"
    #             session.commit()
    #         elif status == "Submitted":
    #             self._resend_submitted_rest_notification_for(participant)
    #             self._message_researcher(self._resubmitted_msg(summary))
    #             logger.warning(
    #                 "Error - submitted notification for participant {} missed. "
    #                 "A replacement notification was created and sent, "
    #                 "but proceed with caution.".format(participant.id)
    #             )
    #         else:
    #             self._send_notification_missing_rest_notification_for(participant)
    #             unsubmitted.append(summary)

    #     disable_hit = self.config.get("disable_when_duration_exceeded")
    #     if disable_hit and unsubmitted:
    #         self._disable_autorecruit()
    #         self.close_recruitment()
    #         pick_one = unsubmitted[0]
    #         # message the researcher about the one of the participants:
    #         self._message_researcher(self._cancelled_msg(pick_one))
    #         # Attempt to force-expire the hit via boto. It's possible
    #         # that the HIT won't exist if the HIT has been deleted manually.
    #         try:
    #             self.mturkservice.expire_hit(pick_one.participant.hit_id)
    #         except MTurkServiceException as ex:
    #             logger.exception(ex)

    # def rejects_questionnaire_from(self, participant):
    #     """Mechanical Turk participants submit their HITs on the MTurk site
    #     (see external_submission_url), and MTurk then sends a notification
    #     to Dallinger which is used to mark the assignment completed.

    #     If a HIT has already been submitted, it's too late to submit the
    #     questionnaire.
    #     """
    #     if participant.status != "working":
    #         return (
    #             "This participant has already sumbitted their HIT "
    #             "on MTurk and can no longer submit the questionnaire"
    #         )

    # def submitted_event(self):
    #     """MTurk will send its own notification when the worker
    #     completes the HIT on that service.
    #     """
    #     return None

    # def reward_bonus(self, assignment_id, amount, reason):
    #     """Reward the Turker for a specified assignment with a bonus."""
    #     try:
    #         return self.mturkservice.grant_bonus(assignment_id, amount, reason)
    #     except MTurkServiceException as ex:
    #         logger.exception(str(ex))

    #     def approve_hit(self, assignment_id):
    #         try:
    #             return self.mturkservice.approve_assignment(assignment_id)
    #         except MTurkServiceException as ex:
    #             logger.exception(str(ex))

    #     def close_recruitment(self):
    #         """Clean up once the experiment is complete.

    #         This may be called before all users have finished so uses the
    #         expire_hit rather than the disable_hit API call. This allows people
    #         who have already picked up the hit to complete it as normal.
    #         """
    #         logger.info(CLOSE_RECRUITMENT_LOG_PREFIX + " mturk")
    #         # We are not expiring the hit currently as notifications are failing
    #         # TODO: Reinstate this
    #         # try:
    #         #     return self.mturkservice.expire_hit(
    #         #         self.current_hit_id(),
    #         #     )
    #         # except MTurkServiceException as ex:
    #         #     logger.exception(str(ex))

    #     @property
    #     def is_sandbox(self):
    #         return self.config.get("mode") == "sandbox"


#     def _build_required_hit_qualifications(self):
#         # The Qualications an MTurk worker must have, or in the case of the
#         # blocklist, not have, in order for them to see and accept the HIT.
#         quals = []
#         reqs = MTurkQualificationRequirements
#         if self.config.get("approve_requirement") is not None:
#             quals.append(reqs.min_approval(self.config.get("approve_requirement")))
#         if self.config.get("us_only"):
#             quals.append(reqs.restrict_to_countries(["US"]))
#         for item in self._config_to_list("mturk_qualification_blocklist"):
#             qtype = self.mturkservice.get_qualification_type_by_name(item)
#             if qtype:
#                 quals.append(reqs.must_not_have(qtype["id"]))
#         if self.config.get("mturk_qualification_requirements", None) is not None:
#             explicit_qualifications = json.loads(
#                 self.config.get("mturk_qualification_requirements")
#             )
#             quals.extend(explicit_qualifications)

#         return quals

#     def _confirm_sns_subscription(self, token, topic):
#         self.mturkservice.confirm_subscription(token=token, topic=topic)

#     def _report_event_notification(self, events):
#         q = _get_queue()
#         for event in events:
#             event_type = event.get("EventType")
#             assignment_id = event.get("AssignmentId")
#             participant_id = None
#             q.enqueue(worker_function, event_type, assignment_id, participant_id)

#     def _mturk_status_for(self, participant):
#         try:
#             assignment = self.mturkservice.get_assignment(participant.assignment_id)
#             status = assignment["status"]
#         except Exception:
#             status = None
#         return status

#     def _disable_autorecruit(self):
#         heroku_app = heroku_tools.HerokuApp(self.config.get("heroku_app_id_root"))
#         args = json.dumps({"auto_recruit": "false"})
#         headers = heroku_tools.request_headers(self.config.get("heroku_auth_token"))
#         requests.patch(heroku_app.config_url, data=args, headers=headers)

#     def _resend_submitted_rest_notification_for(self, participant):
#         q = _get_queue()
#         q.enqueue(
#             worker_function, "AssignmentSubmitted", participant.assignment_id, None
#         )

#     def _send_notification_missing_rest_notification_for(self, participant):
#         q = _get_queue()
#         q.enqueue(
#             worker_function, "NotificationMissing", participant.assignment_id, None
#         )

#     def _config_to_list(self, key):
#         # At some point we'll support lists, so all service code supports them,
#         # but the config system only supports strings for now, so we convert:
#         as_string = self.config.get(key, None)
#         if as_string is None:
#             return []
#         return [item.strip() for item in as_string.split(",") if item.strip()]

#     def _ensure_mturk_qualifications(self, qualifications):
#         """Create MTurk Qualifications for names that don't already exist,
#         but also return names that already do.
#         """
#         result = {"new_qualifications": [], "existing_qualifications": []}
#         for qual in qualifications:
#             name = qual["name"]
#             desc = qual["description"]
#             try:
#                 result["new_qualifications"].append(
#                     {
#                         "name": name,
#                         "id": self.mturkservice.create_qualification_type(name, desc)[
#                             "id"
#                         ],
#                         "available": False,
#                     }
#                 )
#             except DuplicateQualificationNameError:
#                 result["existing_qualifications"].append(name)

#         # We need to make sure the new qualifications are actually ready
#         # for assignment, as there's a small delay.
#         for tries in range(5):
#             for new in result["new_qualifications"]:
#                 if new["available"]:
#                     continue
#                 try:
#                     self.mturkservice.get_qualification_type_by_name(new["name"])
#                 except QualificationNotFoundException:
#                     logger.warn(
#                         "Did not find qualification {}. Trying again...".format(
#                             new["name"]
#                         )
#                     )
#                     time.sleep(1)
#                 else:
#                     new["available"] = True
#             if all([n["available"] for n in result["new_qualifications"]]):
#                 break

#         unavailable = [q for q in result["new_qualifications"] if not q["available"]]
#         if unavailable:
#             logger.warn(
#                 "After several attempts, some qualifications are still not ready "
#                 "for assignment: {}".format(", ".join(unavailable))
#             )
#         # Return just the available among the new ones
#         result["new_qualifications"] = [
#             q for q in result["new_qualifications"] if q["available"]
#         ]

#         return result

#     def _resubmitted_msg(self, summary):
#         templates = MTurkHITMessages.by_flavor(summary, self.config.get("whimsical"))
#         return templates.resubmitted_msg()

#     def _cancelled_msg(self, summary):
#         templates = MTurkHITMessages.by_flavor(summary, self.config.get("whimsical"))
#         return templates.hit_cancelled_msg()

#     def _message_researcher(self, message):
#         try:
#             self.notifies_admin.send(message["subject"], message["body"])
#         except MessengerError as ex:
#             logger.exception(ex)


class LucidRecruiter(BaseLucidRecruiter):
    """
    The production Lucid recruiter.
    Recruit participants from Lucid Marketplace
    """

    nickname = "lucid-recruiter"

    def __init__(self, *args, **kwargs):
        self.base_url = get_base_url()
        super(LucidRecruiter, self).__init__()
