PsyNet shell completion
=======================

This page explains how to enable shell tab completion for the ``psynet`` command.
It provides automatic completion for commands, subcommands, and options.

Files
-----

- ``psynet-completion.bash`` – Bash completion script
- ``psynet-completion.zsh`` – Zsh completion script

Installation
------------

Installation using the PsyNet command (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   psynet install autocomplete

.. note::

   This method works for both editable and non-editable PsyNet installations. It will automatically
   detect your shell and add the appropriate completion setup to your shell configuration file.

Installation using the installation script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run the installation script from the root of the PsyNet directory:

.. code-block:: bash

   ./install-completion.sh

.. note::

   This method _only_ works for editable PsyNet installations. It will automatically detect your shell
   and add the appropriate completion setup to your shell configuration file.

Manual installation
^^^^^^^^^^^^^^^^^^^

If you prefer to install manually, you can source the completion scripts directly from the root of the PsyNet directory:

- For Bash (``~/.bashrc``):

  .. code-block:: bash

     source ./psynet-completion.bash

- For Zsh (``~/.zshrc``):

  .. code-block:: bash

     source ./psynet-completion.zsh

Activate completion
-------------------

After installation, either restart your terminal or reload your shell configuration:

.. code-block:: bash

   source ~/.bashrc  # for bash
   source ~/.zshrc   # for zsh

Usage
-----

Basic command completion
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   psynet <TAB>

This shows all available commands like e.g. ``debug``, ``deploy``, ``estimate``, etc.

Subcommand completion
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   psynet debug <TAB>

Shows available subcommands, e.g. ``local``, ``ssh``, etc.

Option completion
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   psynet debug local --<TAB>

Shows available options for the specific command, e.g. ``--docker``, ``--archive``, etc.

Partial completion
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   psynet d<TAB>

Completes to ``psynet debug`` (or shows other commands starting with ``d``).

Examples
--------

.. code-block:: bash

   # Complete to debug command
   psynet d<TAB>  # → psynet debug

   # Complete to debug local
   psynet debug l<TAB>  # → psynet debug local

   # Complete to debug local with docker option
   psynet debug local --d<TAB>  # → psynet debug local --docker

   # Complete to deploy ssh with app
   psynet deploy s<TAB>  # → psynet deploy ssh
   psynet deploy ssh --a<TAB>  # → psynet deploy ssh --app

   # Complete to lucid commands
   psynet lucid <TAB>  # shows all lucid subcommands

   # Complete to lucid estimate with options
   psynet lucid estimate --l<TAB>  # → psynet lucid estimate --language-code

Troubleshooting
---------------

If completion doesn't work:

1. Make sure the completion script is properly sourced.
2. Try restarting your terminal.
3. For zsh, make sure completion is enabled: ``autoload -U compinit && compinit``.
4. Verify that ``psynet`` is in your ``PATH``: ``which psynet``.
