from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_experiment_module():
    experiment_path = Path(__file__).with_name("experiment.py")
    spec = spec_from_file_location("adaptive_test_catr_experiment", experiment_path)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_catr_smoke_test():
    module = _load_experiment_module()
    theta = module.run_catr_smoke_test()
    assert isinstance(theta, float)
