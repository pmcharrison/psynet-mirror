.. _developer:
.. highlight:: shell

======================
Updating documentation
======================

To update PsyNet's documentation, work from the root of your PsyNet source checkout, e.g.:

.. code-block:: console

  cd ~/PsyNet

The ``docs`` directory and its subdirectories contain files in `rst` format which stands for `reStructuredText`. See `this primer`_ which introduces the most basic syntax elements of `reStructuredText` documents. For a detailed reference check out the `complete technical specification`_.

.. _this primer: https://docutils.readthedocs.io/en/sphinx-docs/user/rst/quickstart.html
.. _complete technical specification: https://docutils.readthedocs.io/en/sphinx-docs/ref/rst/restructuredtext.html

Once you have made changes to one or more `rst` files compile them into `html` files by executing:

.. code-block:: console

  psynet dev docs make

This uses a serial Sphinx build by default to keep generated HTML deterministic. To speed up local preview builds, pass ``--jobs auto``.

Adding or deleting files additionally requires a clean build for the links in the menu to be updated accordingly:

.. code-block:: console

  psynet dev docs make --clean

To open the generated documentation in your browser after a successful build, run:

.. code-block:: console

  psynet dev docs make --open

Before submitting larger documentation changes, it is useful to treat Sphinx warnings as errors:

.. code-block:: console

  psynet dev docs make --strict

The generated HTML is written to ``docs/_build/html/index.html``.

On completion of updating the documentation commit the corresponding `rst` files only. The compiled `html` files in the ``_build`` directory should be left ignored by Git.
