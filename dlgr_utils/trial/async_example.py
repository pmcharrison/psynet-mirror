import time
from dallinger import db

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from dlgr_utils.trial.chain import ChainNetwork

def async_update_network(network_id):
    logger.info("Running async_update_network for network %i, nothing to do.", network_id)
    network = ChainNetwork.query.filter_by(id=network_id).one()
    time.sleep(5)
    network.awaiting_process = False
    db.session.commit()
