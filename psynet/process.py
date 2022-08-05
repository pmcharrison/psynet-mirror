import contextlib
import datetime
import inspect
import io
import threading
import time
import traceback

import dallinger.db
from dallinger import db
from dallinger.db import redis_conn
from rq import Queue
from rq.job import Job
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .data import SQLBase, SQLMixin, register_table
from .field import PythonDict, PythonObject
from .utils import classproperty, get_logger

logger = get_logger()


@register_table
class AsyncProcess(SQLBase, SQLMixin):
    __tablename__ = "async"

    label = Column(String)
    function = Column(PythonObject)
    arguments = Column(PythonDict)
    pending = Column(Boolean)
    finished = Column(Boolean, default=False)
    time_started = Column(DateTime)
    time_finished = Column(DateTime)
    time_taken = Column(Float)

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship(
        "psynet.participant.Participant", backref="async_processes"
    )

    trial_maker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("TrialNetwork", back_populates="async_processes")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship("TrialNode", back_populates="async_processes")

    trial_id = Column(Integer, ForeignKey("info.id"))
    trial = relationship("Trial", back_populates="async_processes")

    response_id = Column(Integer, ForeignKey("response.id"))
    response = relationship(
        "psynet.timeline.Response", back_populates="async_processes"
    )

    asset_key = Column(String, ForeignKey("asset.key"))
    asset = relationship("Asset", back_populates="async_processes")

    def __init__(
        self,
        function,
        arguments=None,
        trial=None,
        response=None,
        participant=None,
        node=None,
        network=None,
        asset=None,
        label=None,
    ):
        if label is None:
            label = function.__name__

        if arguments is None:
            arguments = {}

        if inspect.ismethod(function):
            method_name = function.__name__
            method_caller = function.__self__
            function = getattr(method_caller.__class__, method_name)
            arguments["self"] = method_caller

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

        self.response = response
        if response:
            self.response_id = response.id

        self.infer_missing_parents()
        self.pending = True

        db.session.add(self)
        db.session.commit()

        self.launch()

        db.session.commit()

    def check_function(self, function):
        assert callable(function)
        # if unserialize(serialize(function)) is None:
        #     raise ValueError(
        #         "The provided function could not be serialized. Make sure that the function is defined at the module "
        #         "or class level, rather than being a lambda function or a temporary function defined within "
        #         "another function."
        #     )
        if inspect.ismethod(function):
            raise ValueError(
                "You cannot pass an instance method to an AsyncProcess. ",
                "Try writing a class method or a static method instead.",
            )

    def log_time_started(self):
        self.time_started = datetime.datetime.now()

    def log_time_finished(self):
        self.time_finished = datetime.datetime.now()

    def infer_missing_parents(self):
        if self.asset is not None:
            if not self.participant:
                self.participant = self.asset.participant
            if not self.node:
                self.node = self.asset.node
            if not self.network:
                self.network = self.asset.network
            if not self.response:
                self.response = self.asset.response

        if self.participant is None and self.response is not None:
            self.participant = self.response.participant
        if self.participant is None and self.trial is not None:
            self.participant = self.trial.participant
        if self.node is None and self.trial is not None:
            self.node = self.trial.origin
        if (
            self.participant is None
            and self.node is not None
            and self.node.participant is not None
        ):
            self.participant = self.node.participant
            self.participant_id = self.participant.id
        if self.network is None and self.node is not None:
            self.network = self.node.network

        if self.participant:
            self.participant_id = self.participant.id
        if self.node:
            self.node_id = self.node.id
        if self.network:
            self.network_id = self.network.id
        if self.network:
            self.trial_maker_id = self.network.trial_maker_id

    @property
    def failure_cascade(self):
        """
        These are the objects that will be failed if the process fails. Ultimately we might want to
        add more objects to this list, for example participants, assets, and networks,
        but currently we're not confident that PsyNet supports failing those objects in that kind of way.
        """
        db.session.refresh(self)
        candidates = [self.trial, self.node]
        return [lambda: [obj] for obj in candidates if obj is not None]

    def launch(self):
        raise NotImplementedError

    @classproperty
    def redis_queue(cls):
        return Queue("default", connection=redis_conn)

    @classmethod
    def call_function(cls, process_id):
        """
        Calls the defining function of a given process.
        """
        from .experiment import import_local_experiment

        import_local_experiment()

        process = AsyncProcess.query.filter_by(id=process_id).one()

        function = process.function

        arguments = cls.preprocess_args(process.arguments)

        timer = time.monotonic()
        process.time_started = datetime.datetime.now()
        db.session.commit()

        try:
            function(**arguments)
            process.time_finished = datetime.datetime.now()
            process.time_taken = time.monotonic() - timer
            process.finished = True
        except BaseException as err:
            process.fail(f"Exception in asynchronous process: {repr(err)}")
            raise
        finally:
            process.pending = False
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
    def launch(self):
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


class WorkerAsyncProcess(AsyncProcess):
    redis_job_id = Column(String)
    timeout = Column(Float)  # note -- currently only applies to non-local proceses
    timeout_scheduled_for = Column(DateTime)
    cancelled = Column(Boolean, default=False)

    def __init__(
        self,
        function,
        arguments=None,
        trial=None,
        participant=None,
        node=None,
        network=None,
        asset=None,
        label=None,
        timeout=None,  # <-- new argument for this class
    ):
        self.timeout = timeout
        if timeout:
            self.timeout_scheduled_for = datetime.datetime.now() + datetime.timedelta(
                seconds=timeout
            )

        super().__init__(
            function,
            arguments,
            trial=trial,
            participant=participant,
            node=node,
            network=network,
            asset=asset,
            label=label,
        )

    def launch(self):
        self.redis_job_id = self.redis_queue.enqueue_call(
            func=self.call_function,
            args=(),
            kwargs=dict(process_id=self.id),
            timeout=self.timeout,
        ).id
        db.session.commit()

    @classmethod
    def check_timeouts(cls):
        processes = cls.query.filter(
            ~cls.failed,
            cls.timeout != None,  # noqa -- this is special SQLAlchemy syntax
            cls.timeout_scheduled_for < datetime.datetime.now(),
        ).all()
        for p in processes:
            p.fail(
                "Asynchronous process timed out",
            )
            db.session.commit()

    @property
    def redis_job(self):
        return Job.fetch(self.redis_job_id, connection=redis_conn)

    def cancel(self):
        self.cancelled = True
        self.pending = False
        self.fail("Cancelled asynchronous process")
        self.job.cancel()
        db.session.commit()
