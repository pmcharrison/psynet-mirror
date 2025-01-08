import os
import sys
import tempfile
from collections import OrderedDict

import pexpect
import polib

LOCALES_DIR = "locales"


def get_locales_dir(locales_dir):
    """Get the locales directory."""
    if locales_dir is None:
        from ..utils import LOCALES_DIR

        locales_dir = LOCALES_DIR
    return locales_dir


def new_pot(fpath):
    """Returns an empty pot file."""
    pot = polib.POFile()
    pot.metadata = {
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    pot.encoding = "utf-8"
    pot.metadata_is_fuzzy = ["fuzzy"]
    pot.fpath = fpath
    return pot


def load_po(po_path):
    """Load a pot or po from file."""
    assert po_path.endswith((".po", ".pot")), "po_path must end with .po or .pot"
    assert os.path.exists(po_path), f"File {po_path} does not exist"
    return polib.pofile(po_path)


def get_pot_from_command(cmd, tmp_pot_file):
    """Create a pot file from a command and open."""
    timeout = 60
    p = pexpect.spawn(cmd, timeout=timeout)
    while not p.eof():
        line = p.readline().decode("utf-8")
        # Don't print the line if it's just a message about writing the PO template file
        if not line.startswith("writing PO template file"):
            print(line, end="")
    p.close()
    if p.exitstatus > 0:
        sys.exit(p.exitstatus)
    if os.path.exists(tmp_pot_file):
        pot = load_po(tmp_pot_file)
        os.remove(tmp_pot_file)
        return list(pot)
    else:
        return []


def create_translation_template_with_pybabel(input):
    """Extract translations from a file or multiple files using pybabel."""
    cfg = """
            [jinja2: **.html]
            encoding = utf-8
            """
    with tempfile.TemporaryDirectory() as tempdir:
        tmp_cfg_file = os.path.join(tempdir, "babel.cfg")
        tmp_pot_file = os.path.join(tempdir, "babel.pot")
        with open(tmp_cfg_file, "w") as f:
            f.write(cfg)
        return get_pot_from_command(
            f"pybabel extract -F {tmp_cfg_file} -o {tmp_pot_file} {input}", tmp_pot_file
        )


def create_translation_template_with_xgettext(input_file):
    """Extract translations from a file using xgettext."""
    with tempfile.TemporaryDirectory() as tempdir:
        tmp_pot_file = os.path.join(tempdir, "xgettext.pot")
        return get_pot_from_command(
            f'xgettext -o {tmp_pot_file} {input_file} -L Python --keyword="_p:1c,2"',
            tmp_pot_file,
        )


# def clean_po(po):
#     po = sort_po(po)
#     po = clean_code_occurence_paths_in_po(po)

#     return po


def sort_po(po: polib.POFile) -> polib.POFile:
    """
    Sorts the entries in the po file.

    Each entry might have multiple occurrences, but we sort by the first occurrence
    (i.e. the first time the string appears in the code).
    In particular, we sort first by the file name, then by the line number.
    Note that the file name strings might be absolute paths, which might vary by machine;
    this doesn't matter for the sorting though, as a given po file will only contain paths
    from the same top-level directory.
    """
    po.sort(key=_po_sort_key)
    return po


def make_file_paths_relative(po: polib.POFile) -> polib.POFile:
    cwd = os.getcwd()
    for entry in po:
        for i, _ in enumerate(entry.occurrences):
            full_path, line_number = entry.occurrences[i]
            relative_path = os.path.relpath(full_path, cwd)
            entry.occurrences[i] = (relative_path, line_number)
    return po


def _po_sort_key(entry):
    first_occurrence = entry.occurrences[0]
    path = first_occurrence[0]
    line_number = int(first_occurrence[1])
    return path, line_number


def create_pot(input_path: str, pot_path):
    """
    Extract translations from a file or multiple files using pybabel or xgettext.
    Parameters
    ----------
    input_path :
        path pointing to the file or directory to extract translations from

    pot_path :
        path pointing to the pot file to write to

    Returns
    -------
    Returns the generated pot file
    """
    if not os.path.isabs(input_path):
        input_path = os.path.abspath(input_path)

    entries = []

    if os.path.isdir(input_path):
        entries.extend(_get_entries_from_dir(input_path))
    elif input_path.endswith(".html"):
        entries.extend(_get_html_entries_from_file(input_path))
    elif input_path.endswith(".py"):
        entries.extend(_get_py_entries_from_file(input_path))
    else:
        raise ValueError("Input file must be a Python or HTML file.")

    pot = new_pot(pot_path)
    pot.extend(entries)

    pot = sort_po(pot)
    pot = make_file_paths_relative(pot)

    os.makedirs(os.path.dirname(pot_path), exist_ok=True)
    pot.save(pot_path)

    return pot


def _get_entries_from_dir(input_path):
    entries = []
    entries.extend(_get_html_entries_from_dir(input_path))
    entries.extend(_get_py_entries_from_dir(input_path))

    return entries


def _get_html_entries_from_dir(input_path):
    # pybabel works recursively, so we can just call it on the directory
    return create_translation_template_with_pybabel(input_path)


def _get_html_entries_from_file(input_path):
    return create_translation_template_with_pybabel(input_path)


def _get_py_entries_from_dir(input_path):
    # xgettext does not work recursively, so we need to walk the directory and call it on each file
    entries = []
    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.endswith(".py"):
                entries.extend(_get_py_entries_from_file(os.path.join(root, file)))
    return entries


def _get_py_entries_from_file(input_path):
    return create_translation_template_with_xgettext(input_path)


def remove_line_numbers(po):
    for entry in po:
        # Get unique occurrence paths without line numbers
        paths = sorted(set([path for path, _ in entry.occurrences]))

        # Store file paths without line numbers
        entry.occurrences = [(path, None) for path in paths]
    return po


def remove_unused_translations_po(pot_entries, po):
    """Remove translations which don't occur in the pot file."""
    po_entries = po_to_dict(po)
    entries = []
    for key, pot_entry in pot_entries.items():
        po_entry = po_entries[key]
        po_entry.comment = pot_entry.comment
        entries.append(po_entry)
    po.clear()
    po.extend(entries)
    return po


def po_to_dict(po):
    """Convert a po file to a dictionary. Keys are (msgid, msgctxt) tuples. Makes sure there are no duplicates."""
    entries_dict = OrderedDict()
    for entry in po:
        key = (entry.msgid, entry.msgctxt)
        if key in entries_dict:
            old_entry = entries_dict[key]
            assert old_entry.msgid == entry.msgid
            assert old_entry.msgctxt == entry.msgctxt
            assert old_entry.msgstr == entry.msgstr
        else:
            entries_dict[key] = entry
    return entries_dict


def get_po_path(locale, locales_dir, module):
    return os.path.join(
        get_locales_dir(locales_dir), locale, "LC_MESSAGES", module + ".po"
    )


def compile_mo(po_path):
    """Compile a po file to a mo file and remove fuzzy entries so the translation is recognized properly."""
    po = load_po(po_path)
    mo_path = po_path.replace(".po", ".mo")
    for entry in po:
        entry.flags = (
            []
        )  # Make sure fuzzy entries are excluded, this will lead to the translation not being recognized
    po.save_as_mofile(mo_path)
