.. _developer:
.. highlight:: shell

======================
Updating documentation
======================

To update PsyNet's documentation first change into your project's ``docs`` directory, e.g.:

.. code-block:: console

  cd ~/PsyNet/docs

The ``docs`` directory and its subdirectories contain files in `rst` format which stands for `reStructuredText`. See `this primer`_ which introduces the most basic syntax elements of `reStructuredText` documents. For a detailed reference check out the `complete technical specification`_.

.. _this primer: https://docutils.readthedocs.io/en/sphinx-docs/user/rst/quickstart.html
.. _complete technical specification: https://docutils.readthedocs.io/en/sphinx-docs/ref/rst/restructuredtext.html

Once you have made changes to one or more `rst` files compile them into `html` files by executing

.. code-block:: console

  make html

Adding or deleting files additionally requires the deletion of the ``_build`` directory for the links in the menu to be updated accordingly:

.. code-block:: console

  rm -r _build
  make html

Now open the file ``_build/html/index.html`` in your browser and have a look at the results.

On completion of updating the documentation commit the corresponding `rst` files only. The compiled `html` files in the ``_build`` directory should be left ignored by Git.
