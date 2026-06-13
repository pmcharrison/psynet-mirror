"""Helpers for previewing a single PsyNet page in debug mode."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Optional

MIRRORED_PREVIEW_PATHS = (
    "assets",
    ".gitignore",
    "config.txt",
    "constraints.txt",
    "requirements.txt",
    "static",
    "templates",
)


def parse_page_target(target: str) -> tuple[str, str]:
    """Parse a page factory target.

    Parameters
    ----------
    target
        Target in ``module:attribute`` form. The module part can be an import
        name or a Python file path relative to the experiment directory.

    Returns
    -------
    tuple
        The module target and dotted attribute path.
    """
    module_name, separator, attribute_path = target.partition(":")
    if not separator or not module_name or not attribute_path:
        raise ValueError(
            "Page factory must use MODULE:ATTRIBUTE syntax, for example "
            "`experiment.py:preview_page`."
        )
    return module_name, attribute_path


def load_page_factory(target: str, experiment_root: Path) -> Callable[..., Any]:
    """Load a page factory from ``MODULE:ATTRIBUTE`` syntax."""
    module_name, attribute_path = parse_page_target(target)
    value = _load_module(module_name, experiment_root.resolve())
    for part in attribute_path.split("."):
        value = getattr(value, part)
    return value


def run_minimal_preview_server(
    target: str,
    *,
    experiment_root: Path,
    host: str = "127.0.0.1",
    port: int = 5000,
) -> None:
    """Run a lightweight Flask server that renders one PsyNet page."""
    from dallinger.config import get_config
    from flask import Flask, Response, jsonify, send_file
    from jinja2 import ChoiceLoader, FileSystemLoader

    from psynet.timeline import Page
    from psynet.utils import call_function_with_context, working_directory

    experiment_root = experiment_root.resolve()
    with preview_experiment_directory(target, experiment_root) as preview_root:
        app = Flask(
            __name__,
            static_folder=None,
            template_folder=str(resources.files("psynet") / "templates"),
        )
        template_paths = [
            resources.files("psynet") / "templates",
            resources.files("dallinger") / "frontend" / "templates",
        ]
        experiment_templates = experiment_root / "templates"
        if experiment_templates.exists():
            template_paths.insert(0, experiment_templates)
        app.jinja_loader = ChoiceLoader(
            [FileSystemLoader(str(path)) for path in template_paths]
        )
        app.jinja_env.globals["logo"] = lambda *args, **kwargs: ""
        app.jinja_env.globals["attributes"] = lambda participant: {}

        page_factory = load_page_factory(target, experiment_root)
        participant = _PreviewParticipant()
        experiment = _PreviewExperiment()
        app.jinja_env.globals["experiment"] = experiment

        with working_directory(preview_root):
            config = get_config()
            if not config.ready:
                config.load()
            app.jinja_env.globals["get_from_config"] = config.get

            @app.route("/")
            def index():
                page = call_function_with_context(
                    page_factory,
                    experiment=experiment,
                    participant=participant,
                    assets={},
                    nodes=[],
                )
                if not isinstance(page, Page):
                    raise TypeError(
                        "The preview target must return a PsyNet Page instance "
                        f"in minimal mode, not {type(page).__name__}."
                    )
                page.pre_render()
                return page.render(experiment, participant)

            @app.route("/page.json")
            def page_json():
                page = call_function_with_context(
                    page_factory,
                    experiment=experiment,
                    participant=participant,
                    assets={},
                    nodes=[],
                )
                return jsonify(page.__json__(participant))

            @app.route("/response", methods=["POST"])
            def response():
                return jsonify(
                    {
                        "submission": "preview",
                        "message": "Minimal page preview does not save responses.",
                    }
                )

            @app.route("/timeline/progress_and_reward")
            def progress_and_reward():
                return jsonify(
                    {
                        "progress_percentage": round(participant.progress * 100),
                        "time_reward": participant.time_reward,
                        "performance_reward": participant.performance_reward,
                    }
                )

            @app.route("/static/<path:filename>")
            def static(filename):
                path = _resolve_static_file(filename, experiment_root)
                if path is None:
                    return Response("Not found", status=404)
                return send_file(path)

            click_message = (
                f"Previewing {target} at http://{host}:{port} "
                "using the minimal page server."
            )
            print(click_message)
            app.run(host=host, port=port, debug=True, use_reloader=False)


def build_preview_experiment_source(target: str, experiment_root: Path) -> str:
    """Build the source code for a one-page preview experiment."""
    parse_page_target(target)
    return dedent(
        f"""
        # Auto-generated by `psynet dev preview-page`.
        import importlib
        import importlib.util
        import pathlib
        import sys

        import psynet.experiment
        from psynet.timeline import PageMaker, Timeline
        from psynet.utils import call_function_with_context


        _ORIGINAL_ROOT = pathlib.Path({json.dumps(str(experiment_root.resolve()))})
        _PAGE_TARGET = {json.dumps(target)}


        def _load_module_from_path(path):
            path = pathlib.Path(path)
            if not path.is_absolute():
                path = _ORIGINAL_ROOT / path
            path = path.resolve()
            module_name = "_psynet_page_preview_" + path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not import page preview module from {{path}}.")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module


        def _load_module(module_name):
            if str(_ORIGINAL_ROOT) not in sys.path:
                sys.path.insert(0, str(_ORIGINAL_ROOT))
            if module_name == "experiment":
                return _load_module_from_path(_ORIGINAL_ROOT / "experiment.py")
            if module_name.endswith(".py") or "/" in module_name or "\\\\" in module_name:
                return _load_module_from_path(module_name)
            return importlib.import_module(module_name)


        def _resolve_target():
            module_name, attribute_path = _PAGE_TARGET.split(":", 1)
            value = _load_module(module_name)
            for part in attribute_path.split("."):
                value = getattr(value, part)
            return value


        def _preview_page(experiment, participant):
            return call_function_with_context(
                _resolve_target(),
                experiment=experiment,
                participant=participant,
            )


        class Exp(psynet.experiment.Experiment):
            timeline = Timeline(
                PageMaker(
                    _preview_page,
                    time_estimate=1.0,
                    label="page_preview",
                )
            )
        """
    ).lstrip()


@dataclass
class _PreviewParticipant:
    """Small participant stand-in for rendering preview pages."""

    id: int = 1
    unique_id: str = "preview-unique-id"
    page_uuid: str = "preview-page-uuid"
    assignment_id: str = "preview-assignment"
    hit_id: str = "preview-hit"
    worker_id: str = "preview-worker"
    time_reward: float = 0.0
    performance_reward: float = 0.0
    progress: float = 0.0
    module_state: Any = None
    current_trial: Any = None
    in_module: bool = False

    def __post_init__(self):
        self.var = {}


class _PreviewRecruiter:
    """Recruiter stand-in for non-Lucid template branches."""

    no_focus_timeout_in_s = 0
    aggressive_no_focus_timeout_in_s = 0
    termination_time_in_s = 0
    inactivity_timeout_in_s = 0

    def time_until_termination_in_s(self, assignment_id):
        return 0


class _PreviewExperiment:
    """Small experiment stand-in for rendering preview pages."""

    app_id = "psynet-page-preview"
    css = []
    css_links = []
    supported_locales = ["en"]
    start_experiment_in_popup_window = False
    recruiter = _PreviewRecruiter()

    def __init__(self):
        self.var = SimpleNamespace(has=lambda key: False)

    def with_lucid_recruitment(self):
        return False

    def make_uuid(self):
        return "preview-page-uuid"


def _load_module(module_name: str, experiment_root: Path):
    """Load a module target from an experiment directory."""
    import importlib
    import importlib.util
    import sys

    if str(experiment_root) not in sys.path:
        sys.path.insert(0, str(experiment_root))

    if module_name == "experiment":
        return _load_module_from_path(experiment_root / "experiment.py")
    if module_name.endswith(".py") or "/" in module_name or "\\" in module_name:
        path = Path(module_name)
        if not path.is_absolute():
            path = experiment_root / path
        return _load_module_from_path(path)
    return importlib.import_module(module_name)


def _load_module_from_path(path: Path):
    """Load a module from a Python file path."""
    import importlib.util

    path = path.resolve()
    module_name = "_psynet_page_preview_" + path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import page preview module from {path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_static_file(filename: str, experiment_root: Path) -> Optional[Path]:
    """Resolve a static file from experiment or PsyNet resources."""
    experiment_static = experiment_root / "static" / filename
    if experiment_static.is_file():
        return experiment_static

    for source, destination in _preview_static_mappings():
        destination_path = Path(str(destination).lstrip("/"))
        if destination_path.parts[:1] != ("static",):
            continue
        relative_destination = Path(*destination_path.parts[1:])
        source_path = Path(source)
        if source_path.is_dir():
            try:
                relative_filename = Path(filename).relative_to(relative_destination)
            except ValueError:
                continue
            candidate = source_path / relative_filename
        elif relative_destination == Path(filename):
            candidate = source_path
        else:
            continue
        if candidate.is_file():
            return candidate
    return None


def _preview_static_mappings():
    """Return PsyNet's built-in static resource mappings."""
    from psynet.experiment import Experiment

    return [
        (source, destination)
        for source, destination in Experiment.extra_files()
        if str(destination).startswith("/static/")
    ]


def create_preview_experiment(
    target: str,
    *,
    experiment_root: Path,
    preview_root: Path,
) -> Path:
    """Create a one-page preview experiment directory."""
    experiment_root = experiment_root.resolve()
    preview_root.mkdir(parents=True, exist_ok=True)
    _write_preview_experiment(target, experiment_root, preview_root)
    _mirror_preview_paths(experiment_root, preview_root)
    _write_default_preview_files(preview_root)
    _initialize_preview_git_repository(preview_root)
    return preview_root


@contextmanager
def preview_experiment_directory(
    target: str, experiment_root: Optional[Path] = None
) -> Iterator[Path]:
    """Create a temporary preview experiment directory."""
    experiment_root = Path.cwd() if experiment_root is None else experiment_root
    with tempfile.TemporaryDirectory(prefix="psynet-page-preview-") as tempdir:
        yield create_preview_experiment(
            target,
            experiment_root=experiment_root,
            preview_root=Path(tempdir),
        )


def _write_preview_experiment(
    target: str, experiment_root: Path, preview_root: Path
) -> None:
    """Write the generated ``experiment.py`` file."""
    source = build_preview_experiment_source(target, experiment_root)
    (preview_root / "experiment.py").write_text(source, encoding="utf-8")


def _mirror_preview_paths(experiment_root: Path, preview_root: Path) -> None:
    """Mirror common experiment paths into the preview directory."""
    for name in MIRRORED_PREVIEW_PATHS:
        source = experiment_root / name
        if source.exists():
            _mirror_path(source, preview_root / name)


def _mirror_path(source: Path, destination: Path) -> None:
    """Mirror a file or directory by symlink, falling back to copying."""
    if destination.exists() or destination.is_symlink():
        return

    try:
        os.symlink(source, destination, target_is_directory=source.is_dir())
        return
    except OSError:
        pass

    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)


def _write_default_preview_files(preview_root: Path) -> None:
    """Write minimal experiment files required by ``psynet debug local``."""
    defaults = {
        ".gitignore": "source_code.zip\nserver.log\nlogs.jsonl\n.deploy/\n",
        "config.txt": (
            "[Config]\n"
            "title = PsyNet page preview\n"
            "description = Preview a single PsyNet page.\n"
            "contact_email_on_error = preview@example.com\n"
            "organization_name = PsyNet\n"
            "recruiter = generic\n"
            "currency = $\n"
            "wage_per_hour = 12.0\n"
        ),
        "constraints.txt": "",
        "requirements.txt": "",
    }

    for filename, contents in defaults.items():
        path = preview_root / filename
        if not path.exists() and not path.is_symlink():
            path.write_text(contents, encoding="utf-8")


def _initialize_preview_git_repository(preview_root: Path) -> None:
    """Make the temporary preview directory pass local debug git checks."""
    if (preview_root / ".git").exists():
        return
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=preview_root,
        check=True,
    )
