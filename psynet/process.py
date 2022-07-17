import contextlib
import io
import threading
import time
import traceback
from datetime import datetime

import dallinger.db
import jsonpickle
from dallinger import db
from dallinger.db import redis_conn
from rq import Queue
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .data import SQLBase, SQLMixin, register_table
from .field import PythonDict, PythonObject
from .utils import classproperty, get_logger, import_local_experiment

logger = get_logger()


@register_table
class AsyncProcess(SQLBase, SQLMixin):
    __tablename__ = "async"

    label = Column(String)
    function = Column(PythonObject)
    arguments = Column(PythonDict)
    finished = Column(Boolean, default=False)
    time_started = Column(DateTime)
    time_finished = Column(DateTime)
    time_taken = Column(Float)
    cancelled = Column(Boolean, default=False)

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship(
        "psynet.participant.Participant", backref="async_processes"
    )

    trial_maker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("Network", backref="async_processes")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship("Node", backref="async_processes")

    trial_id = Column(Integer, ForeignKey("info.id"))
    trial = relationship("Trial", backref="async_processes")

    asset_key = Column(String, ForeignKey("asset.key"))
    asset = relationship("Asset", backref="async_processes")

    def __init__(
        self,
        function,
        arguments,
        trial=None,
        participant=None,
        node=None,
        network=None,
        asset=None,
        label=None,
    ):
        if not label:
            label = function.__name__

        self.check_function(function)

        self.label = label
        self.function = function
        self.arguments = arguments

        # TODO - Refactor this and analogous sections in the PsyNet codebase to be more concise
        self.asset = asset
        if asset:
            self.asset_key = asset.key

        self.participant = participant
        if participant:
            self.participant_id = participant.id

        self.network = network
        if network:
            self.network_id = network.id

        self.node = node
        if node:
            self.node_id = node.id

        self.trial = trial
        if trial:
            self.trial_id = trial.id

        self.infer_missing_parents()

        db.session.add(self)
        db.session.commit()

        self.start()

        db.session.commit()

    def check_function(self, function):
        if jsonpickle.decode(jsonpickle.encode(function)) is None:
            raise ValueError(
                "The provided function could not be serialized. Make sure that the function is defined at the module "
                "or class level, rather than being a lambda function or a temporary function defined within "
                "another function."
            )

    def log_time_started(self):
        self.time_started = datetime.now()

    def log_time_finished(self):
        self.time_finished = datetime.now()

    def infer_missing_parents(self):
        if self.asset is not None:
            if not self.participant:
                self.participant = self.asset.participant
            if not self.node:
                self.node = self.asset.node
            if not self.network:
                self.network = self.asset.network

        if self.participant is None and self.trial is not None:
            self.participant = self.trial.participant
        if self.node is None and self.trial is not None:
            self.node = self.trial.origin
        if self.network is None and self.node is not None:
            self.network = self.node.network

        if self.participant:
            self.participant_id = self.participant.id
        if self.node:
            self.node_id = self.node.id
        if self.network:
            self.network_id = self.network.id

    @property
    def failure_cascade(self):
        """
        These are the objects that will be failed if the process fails. Ultimately we might want to
        add more objects to this list, for example participants, assets, and networks,
        but currently we're not confident that PsyNet supports failing those objects in that kind of way.
        """
        db.session.refresh(self)
        candidates = [self.trial, self.node]
        return [[obj] for obj in candidates if obj is not None]

    def start(self):
        raise NotImplementedError

    def cancel(self):
        self.cancelled = True
        self.fail("Cancelled asynchronous process")
        db.session.commit()

    @classproperty
    def redis_queue(cls):
        return Queue("default", connection=redis_conn)

    @classmethod
    def call_function(cls, process_id):
        """
        Calls the defining function of a given process.
        """
        import_local_experiment()

        process = AsyncProcess.query.filter_by(id=process_id).one()

        if process.cancelled:
            raise RuntimeError("Skipping execution as process has been cancelled.")

        function = process.function
        arguments = cls.preprocess_args(process.arguments)

        timer = time.monotonic()
        process.time_started = datetime.now()
        db.session.commit()

        try:
            function(**arguments)
            process.time_finished = datetime.now()
            process.time_taken = time.monotonic() - timer
            process.finished = True
        except BaseException as err:
            process.fail(f"Exception in asynchronous process: {repr(err)}")
            raise
        finally:
            db.session.commit()
            db.session.close()

    @classmethod
    def preprocess_args(cls, arguments):
        """
        Preprocesses the arguments that are passed to the process's function.
        """
        return {key: cls.preprocess_arg(value) for key, value in arguments.items()}

    @classmethod
    def preprocess_arg(cls, arg):
        if isinstance(
            arg, dallinger.db.Base
        ):  # Tests if the object is an SQLAlchemy object
            arg = db.session.merge(arg)  # Reattaches the object to the database session
            db.session.refresh(arg)
        return arg


class LocalAsyncProcess(AsyncProcess):
    def start(self):
        thr = threading.Thread(target=self.thread_function)
        thr.start()

    def thread_function(self):
        try:
            log = io.StringIO()

            with contextlib.redirect_stdout(log):
                try:
                    self.call_function(self.id)
                except BaseException:  # noqa
                    print(traceback.format_exc())

            self.log(log.getvalue())
        finally:
            db.session.commit()
            db.session.close()

    @classmethod
    def log(cls, msg):
        cls.log_to_stdout(msg)
        cls.log_to_redis(msg)

    @classmethod
    def log_to_stdout(cls, msg):
        print(msg)

    @classmethod
    def log_to_redis(cls, msg):
        cls.redis_queue.enqueue_call(
            func=logger.info, args=(), kwargs=dict(msg=msg), timeout=1e10, at_front=True
        )

    def cancel(self):
        raise RuntimeError(
            "It is currently not possible to cancel a LocalAsyncProcess."
        )


class WorkerAsyncProcess(AsyncProcess):
    redis_job_id = Column(String)
    time_out = Column(Float)  # note -- currently only applies to non-local proceses
    time_out_when = Column(DateTime)

    def __init__(
        self,
        timeout,
    ):
        self.timeout = timeout
        if timeout:
            self.timeout_when = datetime.datetime.now() + datetime.timedelta(
                seconds=timeout
            )
        del timeout

        super().__init__(**locals())

    def start(self):
        self.redis_job_id = self.redis_queue.enqueue_call(
            func=self.call_function,
            args=(),
            kwargs=dict(process_id=self.id),
            timeout=self.timeout,
        )
        db.session.commit()

    @classmethod
    def check_timeouts(cls):
        processes = (
            cls.query.filter(
                ~cls.failed,
                ~cls.timeout == None,  # noqa -- this is special SQLAlchemy syntax
                cls.timeout_when < datetime.now(),
            )
            .filter()
            .all()
        )
        for p in processes:
            p.fail("Asynchronous process timed out")
            db.session.commit()
