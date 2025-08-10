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

Easy installation (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run the installation script:

.. code-block:: bash

   ./install-completion.sh

This will automatically detect your shell and add the appropriate completion
setup to your shell configuration file.

Manual installation
^^^^^^^^^^^^^^^^^^^

Method 1: Direct eval (fastest)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add one of the following lines to your shell configuration file.

- For Bash (``~/.bashrc``):

  .. code-block:: bash

     # Guard to avoid errors before the virtualenv is activated
     if command -v psynet >/dev/null 2>&1; then eval "$(_PSYNET_COMPLETE=bash_source psynet)"; fi

- For Zsh (``~/.zshrc``):

  .. code-block:: bash

     # Guard to avoid errors before the virtualenv is activated
     if command -v psynet >/dev/null 2>&1; then eval "$(_PSYNET_COMPLETE=zsh_source psynet)"; fi

Method 2: Source completion scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- For Bash:

  .. code-block:: bash

     # Copy script to system location
     sudo cp psynet-completion.bash /etc/bash_completion.d/psynet

     # Or source it directly in ~/.bashrc
     echo "source $(pwd)/psynet-completion.bash" >> ~/.bashrc

- For Zsh:

  .. code-block:: bash

     # Copy script to system location
     sudo cp psynet-completion.zsh /usr/local/share/zsh/site-functions/_psynet

     # Or source it directly in ~/.zshrc
     echo "source $(pwd)/psynet-completion.zsh" >> ~/.zshrc

Activate completion
-------------------

After installation, either restart your terminal or reload your shell configuration:

.. code-block:: bash

   source ~/.bashrc  # for bash
   source ~/.zshrc   # for zsh

Notes for virtual environments
------------------------------

- If you open a new shell before activating the Python virtual environment that provides ``psynet``, the completion scripts will not error and will auto-register completion once ``psynet`` becomes available (e.g., after running ``source venv/bin/activate``).
- If completion was not registered automatically, you can manually trigger it by sourcing the file again:

  .. code-block:: bash

     # bash
     source /path/to/psynet-completion.bash

     # zsh
     source /path/to/psynet-completion.zsh

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
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   psynet d<TAB>

Completes to ``psynet debug`` (or shows other commands starting with ``d``).

How it works
------------

The completion system uses Click's built-in shell completion functionality:

1. Automatic detection: When you press tab, the shell calls the completion function.
2. Environment variables: The completion function sets environment variables with the current command state.
3. PsyNet integration: The ``psynet`` command detects these environment variables and returns completion suggestions.
4. Dynamic completion: All commands, subcommands, and options are automatically discovered from the Click command structure.

Supported commands and options
------------------------------

Common options
^^^^^^^^^^^^^^

E.g.

- ``--help`` – Show help
- ``--app`` – Experiment app name
- ``--server`` – Server name
- ...

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
2. Check that your shell supports completion (bash or zsh).
3. Try restarting your terminal.
4. For zsh, make sure completion is enabled: ``autoload -U compinit && compinit``.
5. Verify that ``psynet`` is in your ``PATH``: ``which psynet``.

Notes
-----

- The completion scripts use Click's built-in completion system.
- All completion is dynamic and based on the actual command structure.
- File path completion is available for options that expect file paths.
- The scripts work with both the regular ``psynet`` command and the Docker version.
