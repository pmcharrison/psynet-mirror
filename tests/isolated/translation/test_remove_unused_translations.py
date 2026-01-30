import polib

from psynet.translation.utils import po_to_dict, remove_unused_translations_po


def test_remove_unused_translations_keeps_existing_and_adds_missing():
    pot = polib.POFile()
    pot.append(
        polib.POEntry(
            msgid="Hello",
            msgstr="",
            comment="pot hello",
        )
    )
    pot.append(
        polib.POEntry(
            msgid="New text",
            msgstr="",
            comment="pot new",
        )
    )

    po = polib.POFile()
    po.append(
        polib.POEntry(
            msgid="Hello",
            msgstr="Bonjour",
            comment="old comment",
        )
    )

    pot_entries = po_to_dict(pot)

    updated_po = remove_unused_translations_po(pot_entries, po)

    assert [entry.msgid for entry in updated_po] == ["Hello", "New text"]
    assert updated_po[0].msgstr == "Bonjour"
    assert updated_po[0].comment == "pot hello"
    assert updated_po[1].msgstr == ""
    assert updated_po[1].comment == "pot new"
