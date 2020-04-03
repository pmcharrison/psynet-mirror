import time
from dallinger import db

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from dlgr_utils.trial.main import Trial

def async_post_trial(trial_id):
    logger.info("Running async_post_trial for trial %i...", trial_id)
    trial = Trial.query.filter_by(id=trial_id).one()
    time.sleep(1000)
    trial.awaiting_process = False
    db.session.commit()
    