import csv
import io
import os
import tempfile
from typing import List, Optional
from zipfile import ZipFile

import dallinger.models
import pandas
import postgres_copy
import six
import sqlalchemy
from dallinger import db
from dallinger.data import fix_autoincrement
from dallinger.db import Base as SQLBase  # noqa
from dallinger.experiment_server import dashboard
from dallinger.models import Info  # noqa
from dallinger.models import Network  # noqa
from dallinger.models import Node  # noqa
from dallinger.models import Notification  # noqa
from dallinger.models import Question  # noqa
from dallinger.models import Recruitment  # noqa
from dallinger.models import Transformation  # noqa
from dallinger.models import Transmission  # noqa
from dallinger.models import Vector  # noqa
from dallinger.models import SharedMixin, timenow  # noqa
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm.session import close_all_sessions
from sqlalchemy.schema import (
    DropConstraint,
    DropTable,
    ForeignKeyConstraint,
    MetaData,
    Table,
)
from tqdm import tqdm

from . import field
from .field import VarStore
from .utils import classproperty, json_to_data_frame, organize_by_key


def get_db_tables():
    """
    Lists the tables in the database.

    Returns
    -------

    A dictionary where the keys identify the tables and the values are the table objects themselves.
    """
    return db.Base.metadata.tables


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
    Given an SQLAlchemy superclass for SQLAlchemy-mapped objects (e.g. ``Info``),
    looks to see if there is a preferred version of this superclass (e.g. ``Trial``)
    that still covers all instances in the database.

    Parameters
    ----------
    cls :
        Class to simplify

    Returns
    -------

    A simplified class if one was found, otherwise the original class.
    """
    import dallinger.models

    import psynet.timeline

    preferred_superclasses = {
        dallinger.models.Info: psynet.trial.main.Trial,
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


def _db_class_instances_to_json(cls):
    """
    Given a class, retrieves all instances of that class from the database,
    encodes them as JSON-style dictionaries, and returns the resulting list.

    Parameters
    ----------
    cls
        Class to retrieve

    Returns
    -------

    List of dictionaries corresponding to JSON-encoded objects.

    """
    primary_keys = [c.name for c in cls.__table__.primary_key.columns]
    obj_sql = cls.query.order_by(*primary_keys).all()
    if len(obj_sql) == 0:
        print(f"{cls.__name__}: skipped (nothing to export)")
        return []
    else:
        obj_json = [
            _db_instance_to_json(obj) for obj in tqdm(obj_sql, desc=cls.__name__)
        ]
        return obj_json


def _db_instance_to_json(obj):
    """
    Converts an ORM-mapped instance to a JSON-style representation.

    Parameters
    ----------
    obj
        Object to convert

    Returns
    -------

    JSON-style dictionary

    """
    json = obj.__json__()
    if "class" not in json:
        json["class"] = obj.__class__.__name__  # for the Dallinger classes
    return json


def _prepare_db_export():
    """
    Encodes the database to a JSON-style representation suitable for export.

    Returns
    -------

    A dictionary keyed by class names with lists of JSON-style
    encoded class instances as values.
    The keys correspond to the most-specific available class names,
    e.g. ``CustomNetwork`` as opposed to ``Network``.
    """
    superclasses = list(_get_superclasses_by_table().values())
    superclasses.sort(key=lambda cls: cls.__name__)
    res = []
    for superclass in superclasses:
        res.extend(_db_class_instances_to_json(superclass))
    res = organize_by_key(res, key=lambda x: x["class"])
    return res


def dump_db_to_disk(dir):
    """
    Exports all database objects to JSON-style dictionaries
    and writes them to CSV files, one for each class type.

    Parameters
    ----------

    dir
        Directory to which the CSV files should be exported.
    """
    objects_by_class = _prepare_db_export()

    for cls, objects in objects_by_class.items():
        filename = cls + ".csv"
        filepath = os.path.join(dir, filename)
        with open(filepath, "w") as file:
            json_to_data_frame(objects).to_csv(file, index=False)


class SQLMixinDallinger(SharedMixin):
    """
    We apply this Mixin class when subclassing Dallinger classes,
    for example ``Network`` and ``Info``.
    It adds a few useful exporting features,
    but most importantly it adds automatic mapping logic,
    so that polymorphic identities are constructed automatically from
    class names instead of having to be specified manually.
    For example:

    ```py
    from dallinger.models import Info

    class CustomInfo(Info)
        pass
    ```
    """

    polymorphic_identity = (
        None  # set this to a string if you want to customize your polymorphic identity
    )
    __extra_vars__ = {}

    @property
    def var(self):
        return VarStore(self)

    def __json__(self):
        """
        Determines the information that is shown for this object in the dashboard
        and in the csv files generated by ``psynet export``.
        """
        x = {c: getattr(self, c) for c in self.sql_columns}

        x["class"] = self.__class__.__name__

        # Dallinger also needs us to set a parameter called ``object_type``
        # which is used to determine the visualization method.
        base_class = get_sql_base_class(self)
        x["object_type"] = base_class.__name__ if base_class else x["type"]

        field.json_add_extra_vars(x, self)
        field.json_clean(x, details=True)
        field.json_format_vars(x)

        return x

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
        if cls.polymorphic_identity and not cls.ancestor_has_same_polymorphic_identity(
            cls.polymorphic_identity
        ):
            polymorphic_identity = cls.polymorphic_identity
        else:
            # Otherwise, take the polymorphic_identity from the class name
            if cls.ancestor_has_same_polymorphic_identity(cls.__name__):
                raise RuntimeError(
                    f"Two distinct ORM-mapped classes share the same class name: {cls.__name__}. "
                    "You should either give them different class names or different polymorphic_identity values."
                )
            polymorphic_identity = cls.__name__

        x = {"polymorphic_identity": polymorphic_identity}
        if not cls.inherits_table:
            x["polymorphic_on"] = cls.type
        return x


class SQLMixin(SQLMixinDallinger):
    """
    We apply this mixin when creating our own SQL-backed
    classes from scratch. For example:

    ```
    from psynet.data import SQLBase, SQLMixin, register_table

    @register_table
    class Bird(SQLBase, SQLMixin):
        __tablename__ = "bird"

    class Sparrow(Bird):
        pass
    ```
    """

    @declared_attr
    def type(cls):
        return Column(String(50))


def init_db(drop_all=False, bind=db.engine):
    # Without these preliminary steps, the process can freeze --
    # https://stackoverflow.com/questions/24289808/drop-all-freezes-in-flask-with-sqlalchemy
    db.session.commit()
    close_all_sessions()

    dallinger.db.init_db(drop_all, bind)


def drop_all_db_tables(bind=db.engine):
    """
    Drops all tables from the Postgres database.
    Includes a workaround for the fact that SQLAlchemy doesn't provide a CASCADE option to ``drop_all``,
    which was causing errors with Dallinger's version of database resetting in ``init_db``.

    (https://github.com/pallets-eco/flask-sqlalchemy/issues/722)
    """
    engine = bind

    con = engine.connect()
    trans = con.begin()
    inspector = sqlalchemy.inspect(engine)

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

    for fkey in all_fkeys:
        con.execute(DropConstraint(fkey))

    for table in tables:
        con.execute(DropTable(table))

    trans.commit()


dallinger.db.Base.metadata.drop_all = drop_all_db_tables


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
    SQLAlchemy table.
    For example:

    ``` py
    @register_table
    class Bird(SQLBase, SQLMixin):
        __tablename__ = "bird"
    ```
    """
    _sql_psynet_base_classes[cls.__tablename__] = cls
    setattr(dallinger.models, cls.__name__, cls)
    update_dashboard_models()
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
            }
            .union({cls.__name__ for cls in _sql_psynet_base_classes.values()})
            .difference({"_Response"})
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
        postgres_copy.copy_from(
            file, model, engine, columns=columns, format="csv", HEADER=False
        )
        if "id" in inspector.get_columns(model.__table__):
            fix_autoincrement(engine, model.__table__.name)


def patch_csv(infile, outfile, clear_columns, replace_columns):
    df = pandas.read_csv(infile)

    _replace_columns = {**{col: pandas.NA for col in clear_columns}, **replace_columns}

    for col, value in _replace_columns.items():
        df[col] = value

    df.to_csv(outfile, index=False)


def ingest_zip(path, engine=None):
    """
    Given a path to a zip file created with `export()`, recreate the
    database with the data stored in the included .csv files.
    This is a patched version of dallinger.data.ingest_zip that incorporates
    support for custom tables.
    """

    if engine is None:
        engine = db.engine

    inspector = sqlalchemy.inspect(engine)
    all_table_names = inspector.get_table_names()

    import_order = [
        "network",
        "participant",
        "node",
        "info",
        "notification",
        "question",
        "transformation",
        "vector",
        "transmission",
    ]

    for n in all_table_names:
        if n not in import_order:
            import_order.append(n)

    with ZipFile(path, "r") as archive:
        filenames = archive.namelist()

        for tablename in import_order:
            filename_template = f"data/{tablename}.csv"

            matches = [f for f in filenames if filename_template in f]
            if len(matches) == 0:
                continue
            elif len(matches) > 1:
                raise IOError(
                    f"Multiple matches for {filename_template} found in archive: {matches}"
                )
            else:
                filename = matches[0]

            model = sql_base_classes()[tablename]

            file = archive.open(filename)
            if six.PY3:
                file = io.TextIOWrapper(file, encoding="utf8", newline="")
            ingest_to_model(file, model, engine)


dallinger.data.ingest_zip = ingest_zip
dallinger.data.ingest_to_model = ingest_to_model
