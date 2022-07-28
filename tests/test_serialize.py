import pytest

import psynet.field  # noqa
from psynet.serialize import serialize, unserialize
from psynet.trial.static import StaticTrial, Stimulus
from psynet.utils import import_local_experiment


@pytest.mark.usefixtures("demo_static")
class Test:
    def test_psynet_method(self):
        import psynet.trial.main

        f = psynet.trial.main.Trial.call_async_post_trial
        f_serialized = serialize(f)
        assert (
            f_serialized
            == '{"py/function": "psynet.trial.main.Trial.call_async_post_trial"}'
        )
        assert unserialize(f_serialized) == f

    # def test_custom_sql_classes(self, trial, node, network, participant):
    #     unserialize('{"py/function": "dallinger_experiment.test.my_add"}')
    #
    #     self.check_mappers()
    #
    #     classes = get_custom_sql_classes()
    #
    #     desired = [
    #         "AnimalTrial",
    #     ]
    #
    #     assert desired == list(classes.keys())
    #     assert desired == list([c.__name__ for c in classes.values()])
    #
    #     self.check_mappers()

    def test_config(self, trial, node, network, participant):
        # Checking that loading Dallinger config doesn't mess up the mappers in the way it used to
        self.check_mappers()

        import_local_experiment()

        from dallinger.config import get_config

        config = get_config()

        if not config.ready:
            config.load()

        self.check_mappers()

    def test_serialize_sql(self, trial, node, network, participant):
        # from psynet.utils import

        trial_serialized = serialize(trial)
        assert (
            trial_serialized
            == '{"py/object": "dallinger_experiment.experiment.AnimalTrial", "identifiers": {"id": 1}}'
        )

        trial_unserialized = unserialize(trial_serialized)
        assert isinstance(trial_unserialized, StaticTrial)
        assert trial.id == 1
        assert isinstance(trial.origin, Stimulus)

        self.check_mappers()

    def test_serialize_custom_function(self):
        exp = import_local_experiment()

        f = exp["module"].test.my_add
        f_serialized = serialize(f)

        assert f_serialized == '{"py/function": "dallinger_experiment.test.my_add"}'

        f_unserialized = unserialize(f_serialized)
        assert f_unserialized(1, 4) == 5

        self.check_mappers()

    def test_serialize_custom_object(self):
        exp = import_local_experiment()

        obj = exp["module"].test.MyClass(x=3)
        obj_serialized = serialize(obj)

        assert (
            obj_serialized
            == '{"py/object": "dallinger_experiment.test.MyClass", "x": 3}'
        )

        obj_unserialized = unserialize(obj_serialized)
        assert isinstance(obj_unserialized, exp["module"].test.MyClass)

        self.check_mappers()

    def test_serialize_custom_method(self):
        exp = import_local_experiment()

        method = exp["module"].test.MyClass.add
        method_serialized = serialize(method)

        assert (
            method_serialized
            == '{"py/function": "dallinger_experiment.test.MyClass.add"}'
        )

        method_unserialized = unserialize(method_serialized)
        assert method_unserialized == exp["module"].test.MyClass.add

        self.check_mappers()

    def test_serialized_unknown_module(self):
        object_serialized = '{"py/object": "dallinger_experiment.abc.MyClass", "x": 3}'

        with pytest.raises(AttributeError):
            unserialize(object_serialized)

        # assert (
        #     str(e.value)
        #     == f"Tried to unserialize a custom object (dallinger_experiment.abc.MyClass) but couldn't find the requested module: 'abc'. You may need to make sure it's imported in experiment.py."
        # )

        self.check_mappers()

    def test_serialize_unknown_object(self):
        object_serialized = '{"py/object": "dallinger_experiment.test.ABC"}'

        with pytest.raises(AttributeError):
            unserialize(object_serialized)

        # assert (
        #     str(e.value)
        #     == f"Tried to unserialize a custom object (dallinger_experiment.test.ABC) but couldn't find the requested object: 'ABC'"
        # )

        self.check_mappers()

    def check_mappers(self):
        # If we don't manage the imports correctly, we can end up with a nasty bug where
        # SQLAlchemy Base.registry.mappers stops working, and instead throws an error
        # when you try to call it.
        from dallinger.db import Base

        assert Base.registry.mappers

        # animal_trial_mappers = [
        #     m for m in Base.registry.mappers if m.class_.__name__ == "AnimalTrial"
        # ]
        # assert len(animal_trial_mappers) == 1
