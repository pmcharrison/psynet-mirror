import click

from psynet.command_line import psynet as psynet_cli


@psynet_cli.group("translation")
def translation():
    pass

    """Translation management commands."""


def parse_list(value):
    return value.replace(",", " ").split()


options = {
    "experiment": click.option(
        "--experiment",
        help="Whether to translate the experiment directory",
        default=False,
        is_flag=True,
    ),
    "languages": click.option(
        "--languages",
        help="The target languages, specified as a space or comma-separated list of language codes",
        type=parse_list,
    ),
    "packages": click.option(
        "--packages",
        help="The target packages, specified as a space or comma-separated list of package names",
        default="",
        type=parse_list,
    ),
}


@translation.command("generate")
@options["experiment"]
@options["packages"]
@options["languages"]
def generate(experiment, packages, languages):
    """
    Generate translations for the specified experiment or packages.
    Translation is done automatically using LLMs.
    The translation files will be saved in the current directory.

    Most users will want to run this command with the `--experiment` option.
    If the selected languages are not included in the PsyNet package,
    users will additionally need to specify PsyNet in the `--packages` option.

    Example
    -------

    psynet translation generate --experiment --languages fr
        Translate the current experiment to French.

    psynet translation generate --experiment --packages psynet --languages fr
        Translate both the current experiment and the PsyNet package to French.
    """
    for language in languages:
        if experiment:
            click.echo(f"Translating experiment to {language}...")
            translate_experiment(language)

        for package in packages:
            click.echo(f"Translating {package} package to {language}...")
            translate_package(package, language)


@translation.command("export")
@options["packages"]
@options["languages"]
def export(packages, languages):
    """
    Exports package translations back to the original packages.
    The packages need to be installed in editable mode.

    Examples
    --------

    psynet translation export --packages psynet --languages fr
        Export French translations back to the PsyNet package.
    """
    for language in languages:
        for package in packages:
            click.echo(
                f"Exporting {language} translations to the {package} package ..."
            )
            export_package(package, language)


@translation.command("import")
@options["packages"]
@options["languages"]
def import_(packages, languages):
    """
    Imports translations from the specified packages into the current experiment directory.
    This command is useful if you want to use the packages' original translations as a starting point,
    but then modify them yourself.

    Examples
    --------

    psynet translation import --packages psynet --languages fr
        Import French translations from the PsyNet package.
    """
    for language in languages:
        for package in packages:
            click.echo(
                f"Importing {language} translations from the {package} package ..."
            )
            import_package(package, language)


@translation.command("check")
def check():
    """Check translation files for issues."""
    pass


def translate_experiment(languages):
    pass


def translate_package(package, languages):
    pass


def export_package(package, language):
    pass


def import_package(package, language):
    pass
