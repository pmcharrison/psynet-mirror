import contextlib
import csv
import io
import os
import shutil
import tempfile
from typing import List, Optional
from zipfile import ZipFile

import dallinger.data
import dallinger.models
import sqlalchemy
from dallinger import db
from dallinger.command_line.docker_ssh import CONFIGURED_HOSTS
from dallinger.data import fix_autoincrement
from dallinger.db import Base as SQLBase  # noqa
from dallinger.experiment_server import dashboard
from dallinger.models import (  # noqa
    Info,  # noqa
    Network,  # noqa
    Node,  # noqa
    Notification,  # noqa
    Question,  # noqa
    Recruitment,  # noqa
    SharedMixin,
    Transformation,  # noqa
    Transmission,  # noqa
    Vector,  # noqa
    timenow,
)
from dallinger.postgres_copy import copy_from as postgres_copy_from
from dallinger.utils import classproperty
from jsonpickle.util import importable_name
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import deferred
from sqlalchemy.orm.session import close_all_sessions
from sqlalchemy.schema import (
    DropConstraint,
    DropTable,
    ForeignKeyConstraint,
    MetaData,
    Table,
)

from . import field
from .field import PythonDict, is_basic_type
from .utils import organize_by_key


def get_db_tables():
    """
    Lists the tables in the database.

    Returns
    -------

    A dictionary where the keys identify the tables and the values are the table objects themselves.
    """
    return db.Base.metadata.tables


def get_primary_key_values(instance):
    """
    Return primary key values for an ORM instance.
    """
    primary_key_cols = [
        column.name for column in instance.__class__.__table__.primary_key.columns
    ]
    return {key: getattr(instance, key) for key in primary_key_cols}


def _get_superclasses_by_table():
    """
    Returns
    -------

    A dictionary where the keys enumerate the different tables in the database
    and the values correspond to the superclasses for each of those tables.
    """

    mappers = list(db.Base.registry.mappers)
    mapped_classes = [m.class_ for m in mappers]

    mapped_classes_by_table = organize_by_key(mapped_classes, lambda x: x.__tablename__)
    superclasses_by_table = {
        cls: _get_superclass(class_list)
        for cls, class_list in mapped_classes_by_table.items()
    }
    return superclasses_by_table


def _get_superclass(class_list):
    """
    Given a list of classes, returns the class in that list that is a superclass of
    all other classes in that list. Assumes that exactly one such class exists
    in that list; if this is not true, an AssertionError is raised.

    Parameters
    ----------
    classes :
        List of classes to check.

    Returns
    -------

    A single superclass.
    """
    superclasses = [cls for cls in class_list if _is_global_superclass(cls, class_list)]
    assert len(superclasses) == 1
    cls = superclasses[0]
    cls = _get_preferred_superclass_version(cls)
    return cls


def _is_global_superclass(x, class_list):
    """
    Parameters
    ----------

    x :
        Class to test

    class_list :
        List of classes to test against

    Returns
    -------

    ``True`` if ``x`` is a superclass of all elements of ``class_list``, ``False`` otherwise.
    """
    return all([issubclass(cls, x) for cls in class_list])


def _get_preferred_superclass_version(cls):
    """
    Given an SQLAlchemy superclass for SQLAlchemy-mapped objects (e.g. ``_Response``),
    looks to see if there is a preferred version of this superclass (e.g. ``Response``)
    that still covers all instances in the database.

    Parameters
    ----------
    cls :
        Class to simplify

    Returns
    -------

    A simplified class if one was found, otherwise the original class.
    """
    import psynet.timeline

    preferred_superclasses = {
        psynet.bot.Bot: psynet.participant.Participant,
        psynet.timeline._Response: psynet.timeline.Response,
    }

    proposed_cls = preferred_superclasses.get(cls)
    if proposed_cls:
        proposed_cls = preferred_superclasses[cls]
        n_original_cls_instances = cls.query.count()
        n_proposed_cls_instances = proposed_cls.query.count()
        proposed_cls_has_equal_coverage = (
            n_original_cls_instances == n_proposed_cls_instances
        )
        if proposed_cls_has_equal_coverage:
            return proposed_cls
    return cls


def copy_db_table_to_csv(tablename, path):
    with tempfile.TemporaryDirectory() as tempdir:
        dallinger.data.copy_db_to_csv(db.db_url, tempdir)
        temp_filename = f"{tablename}.csv"
        shutil.copyfile(os.path.join(tempdir, temp_filename), path)


class InvalidDefinitionError(ValueError):
    """
    InvalidDefinitionError class
    """

    pass


checked_classes = set()


class SQLMixinDallinger(SharedMixin):
    """
    We apply this Mixin class when subclassing Dallinger classes,
    for example ``Network`` and ``Info``.
    It adds a few useful exporting features,
    but most importantly it adds automatic mapping logic,
    so that polymorphic identities are constructed automatically from
    class names instead of having to be specified manually.
    For example:

    ::

        from dallinger.models import Info

        class CustomInfo(Info)
            pass

    """

    polymorphic_identity = (
        None  # set this to a string if you want to customize your polymorphic identity
    )

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        cls.check_validity()
        return self

    def __repr__(self):
        try:
            id_ = self.id
        except sqlalchemy.orm.exc.DetachedInstanceError:
            id_ = "?"
        base_class = get_sql_base_class(self).__name__
        cls = self.__class__.__name__
        return "{}-{}-{}".format(base_class, id_, cls)

    @declared_attr
    def vars(cls):
        return deferred(Column(PythonDict, default=lambda: {}, server_default="{}"))

    @property
    def var(self):
        from .field import VarStore

        return VarStore(self)

    def to_dict(self):
        """
        Determines the information that is shown for this object in the dashboard.
        """
        from psynet.trial import ChainNode
        from psynet.trial.main import GenericTrialNode

        x = {c: getattr(self, c) for c in self.sql_columns}

        x["class"] = self.__class__.__name__

        # This is a little hack we do for compatibility with the Dallinger
        # network visualization, which relies on sources being explicitly labeled.
        if isinstance(self, GenericTrialNode) or (
            isinstance(self, ChainNode) and self.degree == 0
        ):
            x["type"] = "TrialSource"
        else:
            x["type"] = x["class"]

        # Dallinger also needs us to set a parameter called ``object_type``
        # which is used to determine the visualization method.
        base_class = get_sql_base_class(self)
        x["object_type"] = base_class.__name__ if base_class else x["type"]

        field.json_clean(x, details=True)
        field.json_format_vars(x)

        return x

    def __json__(self) -> dict:
        "Used to transmit the item to the Dallinger dashboard"
        data = self.to_dict()
        for key, value in data.items():
            if not is_basic_type(value):
                data[key] = repr(value)
        return data

    @classproperty
    def sql_columns(cls):
        return cls.__mapper__.column_attrs.keys()

    @classproperty
    def inherits_table(cls):
        for ancestor_cls in cls.__mro__[1:]:
            if (
                hasattr(ancestor_cls, "__tablename__")
                and ancestor_cls.__tablename__ is not None
            ):
                return True
        return False

    @classmethod
    def ancestor_has_same_polymorphic_identity(cls, polymorphic_identity):
        for ancestor_cls in cls.__mro__[1:]:
            if (
                hasattr(ancestor_cls, "polymorphic_identity")
                and ancestor_cls.polymorphic_identity == polymorphic_identity
            ):
                return True
        return False

    @declared_attr
    def __mapper_args__(cls):
        """
        This programmatic definition of polymorphic_identity and polymorphic_on
        means that users can define new SQLAlchemy classes without any reference
        to these SQLAlchemy constructs. Instead the polymorphic mappers are
        constructed automatically based on class names.
        """
        # If the class has a distinct polymorphic_identity attribute, use that
        cls.check_validity()
        if cls.polymorphic_identity and not cls.ancestor_has_same_polymorphic_identity(
            cls.polymorphic_identity
        ):
            polymorphic_identity = cls.polymorphic_identity
        else:
            # Otherwise, take the polymorphic_identity from the fully qualified class name
            polymorphic_identity = importable_name(cls)
        x = {"polymorphic_identity": polymorphic_identity}
        if not cls.inherits_table:
            x["polymorphic_on"] = cls.type
        return x

    __validity_checks_complete__ = False

    @classmethod
    def check_validity(cls):
        if cls not in checked_classes:
            cls._check_validity()
            checked_classes.add(cls)

    @classmethod
    def _check_validity(cls):
        if cls.defined_in_invalid_location():
            raise InvalidDefinitionError(
                f"Problem detected with the definition of class {cls.__name__}:"
                "You are not allowed to define SQLAlchemy classes in unconventional places, "
                "e.g. as class attributes of other classes, within functions, etc. - "
                "it can cause some very hard to debug problems downstream, "
                "for example silently breaking SQLAlchemy relationship updating. "
                "You should instead define your class at the top level of a Python file."
            )

    @classmethod
    def defined_in_invalid_location(cls):
        from jsonpickle.util import importable_name

        path = importable_name(cls)
        family = path.split(".")
        ancestors = family[:-1]
        parent_path = ".".join(ancestors)

        return parent_path != cls.__module__
        # if "<locals>" in parent_path:
        #     return True
        #
        # parent = loadclass(parent_path)
        # if parent is None or isclass(parent):
        #     return True
        #
        # return False

    def scrub_pii(self, json):
        """
        Removes personally identifying information from the object's JSON representation.
        This is a destructive operation (it changes the input object).
        """
        to_scrub = ["client_ip_address", "worker_id"]
        for key in to_scrub:
            try:
                del json[key]
            except KeyError:
                pass

        return json


#
# @event.listens_for(SQLMixinDallinger, "after_insert", propagate=True)
# def after_insert(mapper, connection, target):
#     # obj = unserialize(serialize(target))
#     old_session = db.session
#     db.session = db.scoped_session(db.session_factory)  # db.create_scoped_session()
#     obj = unserialize(serialize(target))
#     obj.on_creation()
#     # target.on_creation()
#     db.session.commit()
#     db.session = old_session


class SQLMixin(SQLMixinDallinger):
    """
    We apply this mixin when creating our own SQL-backed classes from scratch.
    For example:

    ::

        from psynet.data import SQLBase, SQLMixin, register_table

        @register_table
        class Bird(SQLBase, SQLMixin):
            __tablename__ = "bird"

        class Sparrow(Bird):
            pass

    """

    @declared_attr
    def type(cls):
        return Column(String)


old_init_db = dallinger.db.init_db


def init_db(drop_all=False, bind=db.engine):
    # Without these preliminary steps, the process can freeze --
    # https://stackoverflow.com/questions/24289808/drop-all-freezes-in-flask-with-sqlalchemy
    # We used to call ``db.session.commit()`` here to close pending transactions, but now
    # we don't need to do this because we are using proper session handling.
    close_all_sessions()
    old_init_db(drop_all, bind)
    from .sqlalchemy_profiling import maybe_enable_sqlalchemy_profiling

    # Enable env-driven SQL profiling early so all queries are captured.
    maybe_enable_sqlalchemy_profiling(bind)

    return db.session


dallinger.db.init_db = init_db


def drop_all_db_tables(bind=db.engine):
    """
    Drops all tables from the Postgres database.
    Includes a workaround for the fact that SQLAlchemy doesn't provide a CASCADE option to ``drop_all``,
    which was causing errors with Dallinger's version of database resetting in ``init_db``.

    (https://github.com/pallets-eco/flask-sqlalchemy/issues/722)
    """
    from sqlalchemy.exc import ProgrammingError

    engine = bind

    db.session.commit()

    con = engine.connect()
    trans = con.begin()

    all_fkeys, tables = list_fkeys()

    for fkey in all_fkeys:
        try:
            con.execute(DropConstraint(fkey))
        except ProgrammingError as err:
            if "UndefinedTable" in str(err):
                pass
            else:
                raise

    for table in tables:
        try:
            con.execute(DropTable(table))
        except ProgrammingError as err:
            if "UndefinedTable" in str(err):
                pass
            else:
                raise

    trans.commit()

    # Calling _old_drop_all helps clear up edge cases, such as the dropping of enum types
    _old_drop_all(bind=bind)


def list_fkeys():
    inspector = sqlalchemy.inspect(db.engine)

    # We need to re-create a minimal metadata with only the required things to
    # successfully emit drop constraints and tables commands for postgres (based
    # on the actual schema of the running instance)
    meta = MetaData()

    tables = []
    all_fkeys = []

    for table_name in inspector.get_table_names():
        fkeys = []

        for fkey in inspector.get_foreign_keys(table_name):
            if not fkey["name"]:
                continue

            fkeys.append(ForeignKeyConstraint((), (), name=fkey["name"]))

        tables.append(Table(table_name, meta, *fkeys))
        all_fkeys.extend(fkeys)

    return all_fkeys, tables


_old_drop_all = dallinger.db.Base.metadata.drop_all
dallinger.db.Base.metadata.drop_all = drop_all_db_tables


# @contextlib.contextmanager
# def disable_foreign_key_constraints():
#     db.session.execute("SET session_replication_role = replica;")
#     # connection.execute("SET session_replication_role = replica;")
#     yield
#     db.session.execute("SET session_replication_role = DEFAULT;")


# This would have been useful for importing data, however in practice
# it caused the import process to hang.
#
@contextlib.contextmanager
def disable_foreign_key_constraints():
    db.session.commit()
    # con = db.engine.connect()
    # trans = con.begin()

    all_fkeys, tables = list_fkeys()

    for fkey in all_fkeys:
        # con.execute(DropConstraint(fkey))
        db.session.execute(DropConstraint(fkey))

    db.session.commit()

    yield

    # This code was meant to re-add the constraints afterwards, but it causes an error that we have not been
    # able to debug, so we have disabled it. It should not be too much of a problem, though; SQLAlchemy
    # should protect us from foreign key misuse anyway.
    #
    # for fkey in all_fkeys:
    #     # con.execute(AddConstraint(fkey))
    #     print(fkey)
    #     db.session.execute(AddConstraint(fkey))
    #
    # db.session.commit()

    # trans.commit()


def _sql_dallinger_base_classes():
    """
    These base classes define the basic object relational mappers for the
    Dallinger database tables.

    Returns
    -------

    A dictionary of base classes for Dallinger tables
    keyed by Dallinger table names.
    """
    from .participant import Participant

    return {
        "info": Info,
        "network": Network,
        "node": Node,
        "notification": Notification,
        "participant": Participant,
        "question": Question,
        "recruitment": Recruitment,
        "transformation": Transformation,
        "transmission": Transmission,
        "vector": Vector,
    }


# A dictionary of base classes for additional tables that are defined in PsyNet
# or by individual experiment implementations, keyed by table names.
# See also dallinger_table_base_classes().
_sql_psynet_base_classes = {}


def sql_base_classes():
    """
    Lists the base classes underpinning the different SQL tables used by PsyNet,
    including both base classes defined in Dallinger (e.g. ``Node``, ``Info``)
    and additional classes defined in custom PsyNet tables.

    Returns
    -------

    A dictionary of base classes (e.g. ``Node``), keyed by the corresponding
    table names for those base classes (e.g. `node`).

    """
    return {
        **_sql_dallinger_base_classes(),
        **_sql_psynet_base_classes,
    }


def get_sql_base_class(x):
    """
    Return the SQLAlchemy base class of an object x, returning None if no such base class is found.
    """
    for cls in sql_base_classes().values():
        if isinstance(x, cls):
            return cls
    return None


def register_table(cls):
    """
    This decorator should be applied whenever defining a new
    SQLAlchemy table. For example:

    ::

        @register_table
        class Bird(SQLBase, SQLMixin):
            __tablename__ = "bird"
    """
    _sql_psynet_base_classes[cls.__tablename__] = cls
    setattr(dallinger.models, cls.__name__, cls)
    update_dashboard_models()
    dallinger.data.table_names.append(cls.__tablename__)
    return cls


def update_dashboard_models():
    "Determines the list of objects in the dashboard database browser."
    dashboard.BROWSEABLE_MODELS = sorted(
        list(
            {
                "Participant",
                "Network",
                "Node",
                "Trial",
                "Response",
                "Transformation",
                "Transmission",
                "Notification",
                "Recruitment",
            }.union(
                {cls.__name__ for cls in _sql_psynet_base_classes.values()}
            ).difference({"_Response"})
        )
    )


def ingest_to_model(
    file,
    model,
    engine=None,
    clear_columns: Optional[List] = None,
    replace_columns: Optional[dict] = None,
):
    """
    Imports a CSV file to the database.
    The implementation is similar to ``dallinger.data.ingest_to_model``,
    but incorporates a few extra parameters (``clear_columns``, ``replace_columns``)
    and does not fail for tables without an ``id`` column.

    Parameters
    ----------
    file :
        CSV file to import (specified as a file handler, created for example by open())

    model :
        SQLAlchemy class corresponding to the objects that should be created.

    clear_columns :
        Optional list of columns to clear when importing the CSV file.
        This is useful in the case of foreign-key constraints (e.g. participant IDs).

    replace_columns :
        Optional dictionary of values to set for particular columns.
    """
    if engine is None:
        engine = db.engine

    if clear_columns or replace_columns:
        with tempfile.TemporaryDirectory() as temp_dir:
            patched_csv = os.path.join(temp_dir, "patched.csv")
            patch_csv(file, patched_csv, clear_columns, replace_columns)
            with open(patched_csv, "r") as patched_csv_file:
                ingest_to_model(
                    patched_csv_file, model, clear_columns=None, replace_columns=None
                )
    else:
        inspector = sqlalchemy.inspect(db.engine)
        reader = csv.reader(file)
        columns = tuple('"{}"'.format(n) for n in next(reader))

        with disable_foreign_key_constraints():
            postgres_copy_from(
                file, model, engine, columns=columns, format="csv", HEADER=False
            )

        columns = inspector.get_columns(model.__table__)
        column_names = [x["name"] for x in columns]
        if "id" in column_names:
            id_column = next(
                (column for column in columns if column["name"] == "id"),
                None,
            )
            if id_column and isinstance(id_column["type"], sqlalchemy.Integer):
                fix_autoincrement(engine, model.__table__.name)


def patch_csv(infile, outfile, clear_columns, replace_columns):
    import pandas as pd

    df = pd.read_csv(infile)

    _replace_columns = {**{col: pd.NA for col in clear_columns}, **replace_columns}

    for col, value in _replace_columns.items():
        df[col] = value

    df.to_csv(outfile, index=False)


def ingest_zip(path, engine=None):
    """Recreate the database from an export archive.

    ``path`` may be:

    * an ``export.zip`` (reads ``database/<table>.csv`` members; also accepts
      legacy ``data/<table>.csv`` members);
    * a ``database/`` directory of table CSVs;
    * an extracted export directory containing ``database/``.

    This patches Dallinger's ``ingest_zip`` with support for custom PsyNet
    tables and the flat ``database/`` export layout.
    """
    from .export.paths import (
        find_table_member_in_zip,
        is_zip_path,
        resolve_database_dir,
        table_csv_path,
    )

    if engine is None:
        engine = db.engine

    inspector = sqlalchemy.inspect(engine)
    all_table_names = inspector.get_table_names()

    import_order = [
        "network",
        "participant",
        "response",
        "node",
        "info",
        "trial",
        "notification",
        "question",
        "transformation",
        "vector",
        "transmission",
        "asset",
    ]

    for n in all_table_names:
        if n not in import_order:
            import_order.append(n)

    path = os.path.abspath(os.path.expanduser(path))

    if is_zip_path(path):
        with ZipFile(path, "r") as archive:
            for tablename in import_order:
                member = find_table_member_in_zip(archive, tablename)
                if member is None:
                    continue
                model = sql_base_classes()[tablename]
                file = archive.open(member)
                file = io.TextIOWrapper(file, encoding="utf8", newline="")
                ingest_to_model(file, model, engine)
        return

    database_dir = resolve_database_dir(path)
    for tablename in import_order:
        csv_path = table_csv_path(database_dir, tablename)
        if not os.path.exists(csv_path):
            continue
        model = sql_base_classes()[tablename]
        with open(csv_path, encoding="utf8", newline="") as file:
            ingest_to_model(file, model, engine)


dallinger.data.ingest_zip = ingest_zip
dallinger.data.ingest_to_model = ingest_to_model


def export_assets(
    path,
    collected_assets_only: bool,
    include_on_demand_assets: bool,
    n_parallel=None,
    server=None,
    local=False,
):
    """
    Export selected assets into ``path`` using semantic ``export_path`` trees.

    Callers typically pass ``<export_dir>/assets``. Layout:

    ::

        <path>/
        ├── manifest.csv
        └── <module>/.../<semantic export_path>

    Bytes are still fetched via the content-addressed local cache; the export
    tree itself uses human-readable paths from :attr:`Asset.export_path`.
    """
    from .asset import ExternalAsset, OnDemandAsset

    # Assumes we already have loaded the experiment into the local database,
    # as would be the case if the function is called from psynet export.
    if collected_assets_only:
        # ExperimentAsset covers deposits for this deployment. CachedAsset and
        # ExternalAsset are pre-existing and only included with --assets all.
        # OnDemandAsset subclasses ExperimentAsset but is skipped unless all.
        from .asset import ExperimentAsset as base_class
    else:
        from .asset import Asset as base_class

    assets_root = path
    os.makedirs(assets_root, exist_ok=True)

    # Selected assets are always exported when requested.
    assets = list(db.session.query(base_class).order_by(base_class.id))
    if not include_on_demand_assets:
        assets = [a for a in assets if not isinstance(a, OnDemandAsset)]

    manifest_rows = []
    asset_ids_needing_bytes = []
    for asset in assets:
        row = {
            "id": asset.id,
            "type": getattr(asset, "type", type(asset).__name__),
            "local_key": asset.local_key,
            "export_path": asset.export_path,
            "sha256_contents": asset.sha256_contents,
            "object_path": asset.object_path,
            "extension": asset.extension,
            "is_folder": bool(asset.is_folder),
            "url": asset.url,
            "module_id": asset.module_id,
            "participant_id": asset.participant_id,
            "trial_id": asset.trial_id,
            "node_id": asset.node_id,
            "network_id": asset.network_id,
            "description": asset.description,
        }
        if isinstance(asset, ExternalAsset):
            # External assets are URL-only in the manifest.
            row["object_path"] = None
            row["sha256_contents"] = None
        else:
            # OnDemand assets are already excluded when include_on_demand_assets
            # is false (see filter above).
            asset_ids_needing_bytes.append(asset.id)
        manifest_rows.append(row)

    # TODO: restore parallelism once SSH/export deadlock is fixed.
    from .utils import get_logger

    logger = get_logger()
    if n_parallel and n_parallel > 1:
        logger.warning(
            "Asset export parallelism is currently disabled (sequential export) "
            "to avoid a known deadlock; ignoring requested n_parallel=%s.",
            n_parallel,
        )
    n_assets = len(asset_ids_needing_bytes)
    exported_meta = {}
    for index, asset_id in enumerate(asset_ids_needing_bytes, start=1):
        if n_assets > 1 and (index == 1 or index == n_assets or index % 25 == 0):
            logger.info("Exporting asset %s/%s (id=%s).", index, n_assets, asset_id)
        meta = export_asset(
            asset_id, assets_root, include_on_demand_assets, server, local
        )
        if meta:
            exported_meta[asset_id] = meta

    # Fill manifest digests/paths from export results without mutating Asset rows.
    for row in manifest_rows:
        meta = exported_meta.get(row["id"])
        if not meta:
            continue
        if meta.get("sha256_contents"):
            row["sha256_contents"] = meta["sha256_contents"]
        if meta.get("export_path"):
            row["export_path"] = meta["export_path"]
        if meta.get("object_path"):
            row["object_path"] = meta["object_path"]

    manifest_path = os.path.join(assets_root, "manifest.csv")
    fieldnames = [
        "id",
        "type",
        "local_key",
        "export_path",
        "sha256_contents",
        "object_path",
        "extension",
        "is_folder",
        "url",
        "module_id",
        "participant_id",
        "trial_id",
        "node_id",
        "network_id",
        "description",
    ]
    with open(manifest_path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)


def export_asset(asset_id, assets_root, include_on_demand_assets, server, local):
    """Export one asset's bytes into the semantic export tree.

    For managed assets with a known SHA-256 digest the local cache at
    ``~/psynet-data/cache/assets`` is consulted first; only objects absent
    from the cache are fetched from storage. Cached objects are linked into
    the export directory at the asset's ``export_path`` (hardlink when
    possible, copy otherwise).

    Returns
    -------
    dict or None
        ``sha256_contents`` / ``export_path`` / ``object_path`` for the
        manifest when bytes were exported. Does not mutate Asset database rows.
    """
    from .asset import Asset, ExternalAsset, OnDemandAsset
    from .experiment import import_local_experiment
    from .utils import sha256_directory, sha256_file

    if server is None:
        ssh_host = None
        ssh_user = None
    else:
        server_info = CONFIGURED_HOSTS[server]
        ssh_host = server_info["host"]
        ssh_user = server_info.get("user")

    import_local_experiment()
    a = Asset.query.filter_by(id=asset_id).one()

    if isinstance(a, ExternalAsset):
        return None
    if not include_on_demand_assets and isinstance(a, OnDemandAsset):
        return None

    semantic_path = _semantic_export_path(a)

    try:
        if isinstance(a, OnDemandAsset):
            with tempfile.TemporaryDirectory() as tempdir:
                suffix = a.extension if a.extension else ""
                if a.is_folder:
                    temp_path = os.path.join(tempdir, "folder")
                    os.makedirs(temp_path)
                    a.export(temp_path)
                    digest = sha256_directory(temp_path)
                else:
                    temp_path = os.path.join(tempdir, f"asset{suffix}")
                    a.export(temp_path)
                    digest = sha256_file(temp_path)

                _cache_and_link_into_export(
                    digest,
                    _make_copy_fn(temp_path, a.is_folder),
                    assets_root,
                    semantic_path,
                    is_folder=a.is_folder,
                )
                return {
                    "sha256_contents": digest,
                    "export_path": semantic_path,
                    "object_path": a.object_path,
                }

        if a.sha256_contents:
            # Fast path: digest is known; consult the cache before fetching.
            digest = a.sha256_contents
            _cache_and_link_into_export(
                digest,
                lambda p: a.export(
                    p, ssh_host=ssh_host, ssh_user=ssh_user, local=local
                ),
                assets_root,
                semantic_path,
                is_folder=bool(a.is_folder),
            )
            return {
                "sha256_contents": digest,
                "export_path": semantic_path,
                "object_path": a.object_path,
            }

        # Slow path: no digest known yet — export to a temp location, hash,
        # place in cache, then link into the export tree.
        with tempfile.TemporaryDirectory() as tempdir:
            suffix = a.extension if a.extension else ""
            temp_path = os.path.join(tempdir, f"asset{suffix}")
            a.export(temp_path, ssh_host=ssh_host, ssh_user=ssh_user, local=local)
            digest = (
                sha256_directory(temp_path) if a.is_folder else sha256_file(temp_path)
            )
            _cache_and_link_into_export(
                digest,
                _make_copy_fn(temp_path, bool(a.is_folder)),
                assets_root,
                semantic_path,
                is_folder=bool(a.is_folder),
            )
            return {
                "sha256_contents": digest,
                "export_path": semantic_path,
                "object_path": a.object_path,
            }
    except Exception:
        print(f"An error occurred when trying to export the asset with id: {asset_id}")
        raise


def _semantic_export_path(asset) -> str:
    """Return a relative semantic path for an asset inside the export tree."""
    path = asset.export_path
    if not path:
        path = (
            asset.generate_export_path()
            if hasattr(asset, "generate_export_path")
            else None
        )
    if not path:
        extension = asset.extension or ""
        path = f"asset_{asset.id}{extension}"
    return path.lstrip("/")


def _cache_and_link_into_export(
    digest, fetch_fn, assets_root, semantic_path, *, is_folder: bool
) -> str:
    """Ensure ``digest`` is cached, then hardlink/copy it to ``semantic_path``.

    Returns
    -------
    str
        Relative semantic path under the assets root.
    """
    from .export.asset_cache import ensure_object_in_cache, link_or_copy
    from .utils import make_parents

    cache_path = ensure_object_in_cache(digest, fetch_fn, is_folder=is_folder)
    dest = os.path.join(assets_root, semantic_path)
    if not os.path.exists(dest):
        make_parents(dest)
        link_or_copy(cache_path, dest, is_folder=is_folder)
    return semantic_path


def _make_copy_fn(src_path: str, is_folder: bool):
    """Return a fetch_fn that copies ``src_path`` to a destination path.

    Used as the ``fetch_fn`` argument to
    :func:`~psynet.export.asset_cache.ensure_object_in_cache` when the
    content has already been materialized locally.
    """

    def _fn(dest_path: str) -> None:
        if is_folder:
            shutil.copytree(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)

    return _fn
