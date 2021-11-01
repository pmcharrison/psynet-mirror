import json

import requests

from .utils import get_logger

logger = get_logger()


class LucidServiceException(Exception):
    """Custom exception type"""


class LucidService(object):
    """
    Facade for Lucid Marketplace services provided via its HTTP API.
    """

    def __init__(
        self,
        api_key,
        sandbox=True,
        max_wait_secs=0,
    ):
        self.api_key = api_key
        self.is_sandbox = sandbox
        self.max_wait_secs = max_wait_secs

    @property
    def request_base_url(self):
        url = "https://live.techops.engineering/demand/v2-beta"
        if self.is_sandbox:
            url = "https://sandbox.techops.engineering/demand/v2-beta"
        return url

    def create_survey(
        self,
        live_url,
        name,
    ):
        """
        Create the actual survey and return a dict with its useful properties.
        """

        headers = {
            "Content-type": "application/json",
            "Authorization": self.api_key,
            "Accept": "text/plain",
        }

        # We need to create a project for the survey first
        params = {
            "description": "MCMCP demo",
            "name": "MCMCP demo project",
            "project_owner_id": 38490,  # TODO: Is this correct? Got from dictionary lookup for users
        }

        data = json.dumps(params)
        response = requests.post(
            f"{self.request_base_url}/projects", data=data, headers=headers
        )

        if "id" not in response:
            raise LucidServiceException(
                "'Create project' request was invalid for unknown reason."
            )

        # Now we create the survey
        params = {
            "business_unit_id": 2404,  # TODO: Get business unit id dynamically
            "project_id": response["id"],
            "project_manager_id": 38490,  # TODO: Is this correct? Got from dictionary lookup for users
            "client_cpi_usd": 5,
            "collects_pii": True,
            "expected_completes": 10,
            "expected_completion_loi": 10,
            "expected_incidence_rate": 0.1,
            "fraud_profile": True,
            "fraud_profile_threshold": 13,
            "industry": "education",
            "live_url": live_url,
            "locale": "eng_us",
            "name": name,
            "priority": 13,
            "quantity_calc_type": "prescreens",
            "relevant_id": True,
            "status": "pending",
            "study_type": "ihut",
            "survey_cpi_usd": 5,
            "test_url": "https://www.samplesurvey.com/test",
            "unique_ip": True,
            "unique_pid": True,
            "verify_callback": True,
        }
        data = json.dumps(params)
        response = requests.post(
            f"{self.request_base_url}/surveys", data=data, headers=headers
        )
        logger.info(params)
        logger.info(data)
        logger.info(response)
        logger.info(response.content)
        if "create_date" not in response or "id" not in response:
            raise LucidServiceException(
                "'Create survey' request was invalid for unknown reason."
            )
        return response
        # return self._translate_survey(response)

    def _translate_survey(self, survey):
        if "Keywords" in survey:
            keywords = [w.strip() for w in survey["Keywords"].split(",") if w.strip()]
        else:
            keywords = []
        translated = {
            "id": survey["HITId"],
            "type_id": survey["HITTypeId"],
            "created": survey["CreationTime"],
            "expiration": survey["Expiration"],
            "max_assignments": survey["MaxAssignments"],
            "title": survey["Title"],
            "description": survey["Description"],
            "keywords": keywords,
            "qualification_type_ids": [
                q["QualificationTypeId"] for q in survey["QualificationRequirements"]
            ],
            "reward": float(survey["Reward"]),
            "review_status": survey["HITReviewStatus"],
            "status": survey["HITStatus"],
            "annotation": survey.get("RequesterAnnotation"),
            "worker_url": self._worker_hit_url(survey["HITTypeId"]),
            "assignments_available": survey["NumberOfAssignmentsAvailable"],
            "assignments_completed": survey["NumberOfAssignmentsCompleted"],
            "assignments_pending": survey["NumberOfAssignmentsPending"],
        }

        return translated

    # def confirm_subscription(self, token, topic):
    #     """Called by the MTurkRecruiter Flask route"""
    #     self.sns.confirm_subscription(token=token, topic=topic)

    # def create_qualification_type(self, name, description, status="Active"):
    #     """Create a new qualification Workers can be scored for."""
    #     try:
    #         response = self.lucid.create_qualification_type(
    #             Name=name, Description=description, QualificationTypeStatus=status
    #         )
    #     except Exception as ex:
    #         if "already created a QualificationType with this name" in str(ex):
    #             raise DuplicateQualificationNameError(str(ex))
    #         else:
    #             raise

    #     return self._translate_qtype(response["QualificationType"])

    # def get_qualification_type_by_name(self, name):
    #     """Return a Qualification Type by name. If the provided name matches
    #     more than one Qualification, check to see if any of the results
    #     match the provided name exactly. If there's an exact match, return
    #     that Qualification. Otherwise, raise an exception.
    #     """
    #     max_fuzzy_matches_to_check = 100
    #     query = name.upper()
    #     args = {
    #         "Query": query,
    #         "MustBeRequestable": False,
    #         "MustBeOwnedByCaller": True,
    #         "MaxResults": max_fuzzy_matches_to_check,
    #     }
    #     results = self.lucid.list_qualification_types(**args)["QualificationTypes"]
    #     # This loop is largely for tests, because there's some indexing that
    #     # needs to happen on MTurk for search to work:
    #     start = time.time()
    #     while not results:
    #         elapsed = time.time() - start
    #         if elapsed > self.max_wait_secs:
    #             return None
    #         time.sleep(1)
    #         results = self.lucid.list_qualification_types(**args)["QualificationTypes"]

    #     qualifications = [self._translate_qtype(r) for r in results]
    #     if len(qualifications) > 1:
    #         for qualification in qualifications:
    #             if qualification["name"].upper() == query:
    #                 return qualification

    #         raise MTurkServiceException("{} was not a unique name".format(query))

    #     return qualifications[0]

    # def assign_qualification(self, qualification_id, worker_id, score, notify=False):
    #     """Score a worker for a specific qualification"""
    #     return self._is_ok(
    #         self.lucid.associate_qualification_with_worker(
    #             QualificationTypeId=qualification_id,
    #             WorkerId=worker_id,
    #             IntegerValue=score,
    #             SendNotification=notify,
    #         )
    #     )

    # def assign_named_qualification(self, name, worker_id, score, notify=False):
    #     """Score a worker for a specific named qualification"""
    #     qtype = self.get_qualification_type_by_name(name)
    #     if qtype is None:
    #         raise QualificationNotFoundException(
    #             'No Qualification exists with name "{}"'.format(name)
    #         )
    #     return self._is_ok(
    #         self.lucid.associate_qualification_with_worker(
    #             QualificationTypeId=qtype["id"],
    #             WorkerId=worker_id,
    #             IntegerValue=score,
    #             SendNotification=notify,
    #         )
    #     )

    # def increment_qualification_score(self, qualification_id, worker_id, notify=False):
    #     """Increment the current qualification score for a worker, on a
    #     qualification with the provided ID.
    #     """
    #     try:
    #         current_score = self.current_qualification_score(
    #             qualification_id, worker_id
    #         )
    #     except (WorkerLacksQualification, RevokedQualification):
    #         current_score = 0
    #     new_score = current_score + 1
    #     self.assign_qualification(qualification_id, worker_id, new_score, notify)

    #     return {"qtype": qualification_id, "score": new_score}

    # def increment_named_qualification_score(self, name, worker_id, notify=False):
    #     """Increment the current qualification score for a worker, on a
    #     qualification with the provided name.
    #     """
    #     result = self.current_named_qualification_score(name, worker_id)
    #     current_score = result["score"] or 0
    #     new_score = current_score + 1
    #     qtype_id = result["qtype"]["id"]
    #     self.assign_qualification(qtype_id, worker_id, new_score, notify)

    #     return {"qtype": result["qtype"], "score": new_score}

    # def revoke_qualification(self, qualification_id, worker_id, reason=""):
    #     return self._is_ok(
    #         self.lucid.disassociate_qualification_from_worker(
    #             QualificationTypeId=qualification_id, WorkerId=worker_id, Reason=reason
    #         )
    #     )

    # def current_qualification_score(self, qualification_id, worker_id):
    #     """Return a worker's qualification score as an iteger."""
    #     try:
    #         response = self.lucid.get_qualification_score(
    #             QualificationTypeId=qualification_id, WorkerId=worker_id
    #         )
    #     except ClientError as ex:
    #         error = str(ex)
    #         if "does not exist" in error:
    #             raise WorkerLacksQualification(
    #                 "Worker {} does not have qualification {}.".format(
    #                     worker_id, qualification_id
    #                 )
    #             )
    #         if "operation can be called with a status of: Granted" in error:
    #             raise RevokedQualification(
    #                 "Worker {} has had qualification {} revoked.".format(
    #                     worker_id, qualification_id
    #                 )
    #             )

    #         raise MTurkServiceException(error)
    #     return response["Qualification"]["IntegerValue"]

    # def current_named_qualification_score(self, name, worker_id):
    #     """Return the current score for a worker, on a qualification with the
    #     provided name.
    #     """
    #     qtype = self.get_qualification_type_by_name(name)
    #     if qtype is None:
    #         raise QualificationNotFoundException(
    #             'No Qualification exists with name "{}"'.format(name)
    #         )
    #     try:
    #         score = self.current_qualification_score(qtype["id"], worker_id)
    #     except (WorkerLacksQualification, RevokedQualification):
    #         score = None

    #     return {"qtype": qtype, "score": score}

    # def dispose_qualification_type(self, qualification_id):
    #     """Remove a qualification type we created"""
    #     return self._is_ok(
    #         self.lucid.delete_qualification_type(QualificationTypeId=qualification_id)
    #     )

    # def get_workers_with_qualification(self, qualification_id):
    #     """Get workers with the given qualification."""
    #     done = False
    #     next_token = None
    #     while not done:
    #         if next_token is not None:
    #             response = self.lucid.list_workers_with_qualification_type(
    #                 QualificationTypeId=qualification_id,
    #                 MaxResults=MAX_SUPPORTED_BATCH_SIZE,
    #                 Status="Granted",
    #                 NextToken=next_token,
    #             )
    #         else:
    #             response = self.lucid.list_workers_with_qualification_type(
    #                 QualificationTypeId=qualification_id,
    #                 MaxResults=MAX_SUPPORTED_BATCH_SIZE,
    #                 Status="Granted",
    #             )
    #         if response:
    #             for r in response["Qualifications"]:
    #                 yield {"id": r["WorkerId"], "score": r["IntegerValue"]}
    #         if "NextToken" in response:
    #             next_token = response["NextToken"]
    #         else:
    #             done = True

    # def extend_hit(self, hit_id, number, duration_hours=None):
    #     """Extend an existing HIT and return an updated description"""
    #     self.create_additional_assignments_for_hit(hit_id, number)

    #     if duration_hours is not None:
    #         self.update_expiration_for_hit(hit_id, duration_hours)

    #     return self.get_hit(hit_id)

    # def create_additional_assignments_for_hit(self, hit_id, number):
    #     try:
    #         response = self.lucid.create_additional_assignments_for_hit(
    #             HITId=hit_id,
    #             NumberOfAdditionalAssignments=number,
    #             UniqueRequestToken=self._request_token(),
    #         )
    #     except Exception as ex:
    #         raise MTurkServiceException(
    #             "Error: failed to add {} assignments to HIT: {}".format(number, str(ex))
    #         )
    #     return self._is_ok(response)

    # def update_expiration_for_hit(self, hit_id, hours):
    #     hit = self.get_hit(hit_id)
    #     expiration = datetime.timedelta(hours=hours) + hit["expiration"]
    #     try:
    #         response = self.lucid.update_expiration_for_hit(
    #             HITId=hit_id, ExpireAt=expiration
    #         )
    #     except Exception as ex:
    #         raise MTurkServiceException(
    #             "Failed to extend time until expiration of HIT: {}\n{}".format(
    #                 expiration, str(ex)
    #             )
    #         )
    #     return self._is_ok(response)

    # def disable_hit(self, hit_id, experiment_id):
    #     self.expire_hit(hit_id)
    #     try:
    #         self.sns.cancel_subscription(experiment_id)
    #     except NonExistentSubscription:
    #         pass

    #     try:
    #         result = self.lucid.delete_hit(HITId=hit_id)
    #     except Exception as ex:
    #         if "currently in the state 'Disposed'" in str(ex):
    #             # this means "already deleted"...
    #             return True
    #         raise

    #     return self._is_ok(result)

    # def expire_hit(self, hit_id):
    #     """Expire a HIT, which will change its status to "Reviewable",
    #     allowing it to be deleted.
    #     """
    #     try:
    #         self.lucid.update_expiration_for_hit(HITId=hit_id, ExpireAt=0)
    #     except Exception as ex:
    #         raise MTurkServiceException(
    #             "Failed to expire HIT {}: {}".format(hit_id, str(ex))
    #         )
    #     return True

    # def get_hit(self, hit_id):
    #     return self._translate_hit(self.lucid.get_hit(HITId=hit_id)["HIT"])

    # def get_hits(self, hit_filter=lambda x: True):
    #     done = False
    #     next_token = None
    #     while not done:
    #         if next_token is not None:
    #             response = self.lucid.list_hits(
    #                 MaxResults=MAX_SUPPORTED_BATCH_SIZE, NextToken=next_token
    #             )
    #         else:
    #             response = self.lucid.list_hits(MaxResults=MAX_SUPPORTED_BATCH_SIZE)
    #         for hit in response["HITs"]:
    #             translated = self._translate_hit(hit)
    #             if hit_filter(translated):
    #                 yield translated
    #         if "NextToken" in response:
    #             next_token = response["NextToken"]
    #         else:
    #             done = True

    # def grant_bonus(self, assignment_id, amount, reason):
    #     """Grant a bonus to the MTurk Worker.
    #     Issues a payment of money from your account to a Worker.  To
    #     be eligible for a bonus, the Worker must have submitted
    #     results for one of your HITs, and have had those results
    #     approved or rejected. This payment happens separately from the
    #     reward you pay to the Worker when you approve the Worker's
    #     assignment.
    #     """
    #     assignment = self.get_assignment(assignment_id)
    #     worker_id = assignment["worker_id"]
    #     amount_str = "{:.2f}".format(amount)
    #     try:
    #         return self._is_ok(
    #             self.lucid.send_bonus(
    #                 WorkerId=worker_id,
    #                 BonusAmount=amount_str,
    #                 AssignmentId=assignment_id,
    #                 Reason=reason,
    #                 UniqueRequestToken=self._request_token(),
    #             )
    #         )
    #     except ClientError as ex:
    #         error = "Failed to pay assignment {} bonus of {}: {}".format(
    #             assignment_id, amount_str, str(ex)
    #         )
    #         raise MTurkServiceException(error)

    # def get_assignment(self, assignment_id):
    #     """Get an assignment by ID and reformat the response."""
    #     try:
    #         response = self.lucid.get_assignment(AssignmentId=assignment_id)
    #     except ClientError as ex:
    #         if "does not exist" in str(ex):
    #             return None
    #         raise
    #     return self._translate_assignment(response["Assignment"])

    # def approve_assignment(self, assignment_id):
    #     """Approving an assignment initiates two payments from the
    #     Requester's Amazon.com account:
    #         1. The Worker who submitted the results is paid
    #            the reward specified in the HIT.
    #         2. Amazon Mechanical Turk fees are debited.
    #     """
    #     try:
    #         return self._is_ok(
    #             self.lucid.approve_assignment(AssignmentId=assignment_id)
    #         )
    #     except ClientError as ex:
    #         assignment = self.get_assignment(assignment_id)
    #         raise MTurkServiceException(
    #             "Failed to approve assignment {}, {}: {}".format(
    #                 assignment_id, str(assignment), str(ex)
    #             )
    #         )

    # def _create_notification_subscription(
    #     self, experiment_id, notification_url, hit_type_id
    # ):
    #     topic_arn = self.sns.create_subscription(experiment_id, notification_url)
    #     logger.warning("Updating HIT with confirmed subscription: {}".format(topic_arn))
    #     self.lucid.update_notification_settings(
    #         HITTypeId=hit_type_id,
    #         Notification={
    #             "Destination": topic_arn,
    #             "Transport": "SNS",
    #             "Version": "2014-08-15",
    #             "EventTypes": [
    #                 "AssignmentAccepted",
    #                 "AssignmentAbandoned",
    #                 "AssignmentReturned",
    #                 "AssignmentSubmitted",
    #                 "HITReviewable",
    #                 "HITExpired",
    #             ],
    #         },
    #         Active=True,
    #     )

    # def _register_hit_type(
    #     self, title, description, reward, duration_hours, keywords, qualifications
    # ):
    #     """Register HIT Type for this HIT and return the type's ID, which
    #     is required for creating a HIT.
    #     """
    #     reward = str(reward)
    #     duration_secs = int(datetime.timedelta(hours=duration_hours).total_seconds())
    #     hit_type = self.lucid.create_hit_type(
    #         Title=title,
    #         Description=description,
    #         Reward=reward,
    #         AssignmentDurationInSeconds=duration_secs,
    #         Keywords=",".join(keywords),
    #         AutoApprovalDelayInSeconds=0,
    #         QualificationRequirements=qualifications,
    #     )

    #     return hit_type["HITTypeId"]

    # def _request_token(self):
    #     return str(time.time())

    # def _translate_assignment(self, assignment):
    #     # Returns only a subset of included values since we don't use most
    #     # currently.
    #     translated = {
    #         "id": assignment["AssignmentId"],
    #         "status": assignment["AssignmentStatus"],
    #         "hit_id": assignment["HITId"],
    #         "worker_id": assignment["WorkerId"],
    #     }

    #     return translated

    # def _worker_hit_url(self, type_id):
    #     if self.is_sandbox:
    #         url = "https://workersandbox.lucid.com/projects/{}/tasks"
    #     else:
    #         url = "https://worker.lucid.com/projects/{}/tasks"

    #     return url.format(type_id)

    # def _translate_qtype(self, qtype):
    #     return {
    #         "id": qtype["QualificationTypeId"],
    #         "created": qtype["CreationTime"],
    #         "name": qtype["Name"],
    #         "description": qtype["Description"],
    #         "status": qtype["QualificationTypeStatus"],
    #     }

    # def _is_ok(self, response):
    #     return response == {} or list(response.keys()) == ["ResponseMetadata"]
