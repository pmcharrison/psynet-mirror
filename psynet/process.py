import datetime
import inspect
import os
import threading
import time

import dallinger.db
import sqlalchemy
from dallinger import db
from dallinger.db import redis_conn
from jsonpickle.util import importable_name
from rq import Queue
from rq.job import Job
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import deferred, relationship

from .data import SQLBase, SQLMixin, register_table
from .field import PythonDict, PythonObject
from .utils import call_function, classproperty, get_logger

logger = get_logger()


@register_table
class AsyncProcess(SQLBase, SQLMixin):
    __tablename__ = "process"
    __extra_vars__ = SQLMixin.__extra_vars__.copy()

    label = Column(String)
    function = Column(PythonObject)
    arguments = deferred(Column(PythonDict))
    pending = Column(Boolean)
    finished = Column(Boolean, default=False)
    time_started = Column(DateTime)
    time_finished = Column(DateTime)
    time_taken = Column(Float)
    _unique_key = Column(PythonDict, unique=True)

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant", backref="async_processes"
    )

    trial_maker_id = Column(String, index=True)

    network_id = Column(Integer, ForeignKey("network.id"), index=True)
    network = relationship("TrialNetwork", back_populates="async_processes")

    node_id = Column(Integer, ForeignKey("node.id"), index=True)
    node = relationship("TrialNode", back_populates="async_processes")

    trial_id = Column(Integer, ForeignKey("info.id"), index=True)
    trial = relationship("psynet.trial.main.Trial", back_populates="async_processes")

    response_id = Column(Integer, ForeignKey("response.id"), index=True)
    response = relationship(
        "psynet.timeline.Response", back_populates="async_processes"
    )

    asset_key = Column(String, ForeignKey("asset.key"), index=True)
    asset = relationship("Asset", back_populates="async_processes")

    errors = relationship("ErrorRecord")

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
        unique=False,
        unique_violation_raises_error=False,
    ):
        db.session.commit()

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

        self.infer_participant()
        self.infer_trial_maker_id()
        self.pending = True

        if unique:
            if isinstance(unique, bool):
                self._unique_key = {
                    "label": label,
                    "function": function,
                    "arguments": arguments,
                }
            else:
                self._unique_key = unique

        try:
            db.session.add(self)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError as err:
            if "duplicate key value" in str(err):
                if unique_violation_raises_error:
                    raise RuntimeError(
                        "An asynchronous process has already been triggered with the following specification: "
                        f"{self._unique_key}"
                    )
                else:
                    db.session.rollback()
                    return
            else:
                raise

        self.launch()
        db.session.commit()

    def check_function(self, function):
        from .serialize import serialize, unserialize

        assert callable(function)
        if "<locals>" in importable_name(function):
            raise ValueError(
                "You cannot use a function defined within another function "
                "in an async process."
            )
        if unserialize(serialize(function)) is None:
            raise ValueError(
                "The provided function could not be serialized. Make sure that the function is defined at the module "
                "or class level, rather than being a lambda function or a temporary function defined within "
                "another function."
            )
        if inspect.ismethod(function):
            raise ValueError(
                "You cannot pass an instance method to an AsyncProcess. ",
                "Try writing a class method or a static method instead.",
            )

    def log_time_started(self):
        self.time_started = datetime.datetime.now()

    def log_time_finished(self):
        self.time_finished = datetime.datetime.now()

    def infer_participant(self):
        if self.participant is None:
            for obj in [self.asset, self.trial, self.node, self.network]:
                if obj and hasattr(obj, "participant") and obj.participant:
                    self.participant = obj.participant
                    break
            # For safety...
            if self.participant:
                self.participant_id = self.participant.id

    def infer_trial_maker_id(self):
        for obj in [self.trial, self.node, self.network]:
            if obj and obj.trial_maker_id:
                self.trial_maker_id = obj.trial_maker_id
                return

    @property
    def failure_cascade(self):
        """
        These are the objects that will be failed if the process fails. Ultimately we might want to
        add more objects to this list, for example participants, assets, and networks,
        but currently we're not confident that PsyNet supports failing those objects in that kind of way.
        """
        candidates = [self.trial, self.node]
        return [lambda obj=obj: [obj] for obj in candidates if obj is not None]

    def launch(self):
        raise NotImplementedError

    @classproperty
    def redis_queue(cls):
        return Queue("default", connection=redis_conn)

    @classmethod
    def call_function_with_logger(cls, process_id):
        cls.call_function(process_id)

    @classmethod
    def call_function(cls, process_id):
        """
        Calls the defining function of a given process
        """
        # cls.log(f"Calling function for process_id: {process_id}")
        print("\n")
        logger.info(f"Calling function for process_id: {process_id}")

        from psynet.experiment import get_experiment

        experiment = get_experiment()

        process = AsyncProcess.query.filter_by(id=process_id).one()

        try:
            function = process.function

            arguments = cls.preprocess_args(process.arguments)

            timer = time.monotonic()
            process.time_started = datetime.datetime.now()
            db.session.commit()

            call_function(function, **arguments)

            process.time_finished = datetime.datetime.now()
            process.time_taken = time.monotonic() - timer
            process.pending = False
            process.finished = True

            from psynet.trial.main import Trial

            if "self" in arguments and isinstance(arguments["self"], Trial):
                arguments["self"].check_if_can_mark_as_finalized()

        except Exception as err:
            if os.getenv("PASSTHROUGH_ERRORS"):
                raise
            if not isinstance(err, experiment.HandledError):
                experiment.handle_error(err, process=process)
            try:
                process.fail(f"Exception in asynchronous process: {repr(err)}")
            except Exception:
                experiment.handle_error(err, process=process)
                process.failed = True
            db.session.commit()
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

    @classmethod
    def log(cls, msg):
        raise NotImplementedError

    @classmethod
    def log_to_stdout(cls, msg):
        print(msg)

    @classmethod
    def log_to_redis(cls, msg):
        return
        cls.redis_queue.enqueue_call(
            func=logger.info, args=(), kwargs=dict(msg=msg), timeout=1e10, at_front=True
        )


class LocalAsyncProcess(AsyncProcess):
    def launch(self):
        thr = threading.Thread(
            target=self.thread_function, kwargs={"process_id": self.id}
        )
        thr.start()

    @classmethod
    def thread_function(cls, process_id):
        try:
            cls.call_function_with_logger(process_id)
        finally:
            db.session.commit()
            db.session.close()

    @classmethod
    def call_function_with_logger(cls, process_id):
        cls.call_function(process_id)

        # log = io.StringIO()
        # try:
        #     with contextlib.redirect_stdout(log):
        #         # yield
        #         cls.call_function(process_id)
        # finally:
        #     cls.log_to_redis(log.getvalue())

        # with cls.log_output():
        #     cls.call_function(process_id)

    # @classmethod
    # @contextlib.contextmanager
    # def log_output(cls):
    #     log = io.StringIO()
    #     try:
    #         with contextlib.redirect_stdout(log):
    #             yield
    #     finally:
    #         cls.log_to_redis(log.getvalue())

    # @classmethod
    # def log(cls, msg):
    #     cls.log_to_redis(msg)


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
        unique=False,
        unique_violation_raises_error=False,
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
            unique=unique,
            unique_violation_raises_error=unique_violation_raises_error,
        )

    def launch(self):
        self.redis_job_id = self.redis_queue.enqueue_call(
            func=self.call_function_with_logger,
            args=(),
            kwargs=dict(process_id=self.id),
            timeout=self.timeout,
        ).id
        db.session.commit()

    @classmethod
    def check_timeouts(cls):
        processes = cls.query.filter(
            cls.pending,
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

    # @classmethod
    # def log(cls, msg):
    #     cls.log_to_stdout(msg)
