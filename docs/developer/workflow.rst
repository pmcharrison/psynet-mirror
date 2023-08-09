.. _developer:
.. highlight:: shell

==================
Developer workflow
==================

Git comes into its own in collaborative software development. We use it in PsyNet to enable multiple developers to work independently on different new features, to review each others’ contributions, and to eventually combine these features together to produce new PsyNet releases.

We have a particular standardized workflow for making contributions to PsyNet. This workflow is similar to workflows used by many software projects around the world, so if you get some experience making contributions to PsyNet, your experience should generalize well to other projects in the future.

PsyNet branches
###############

The branches in the PsyNet repository fall into two main categories:

#. The master branch
#. The feature/bugfix branches

The **master branch** is the default branch, like in most Git repositories. Each commit in the master branch typically corresponds to an individual numbered release in PsyNet, for example v10.2.0.

Each **feature/bugfix branch** is responsible for implementing a particular new feature or fixing a bug. These branches are typically created by branching off the master branch. The programmer works on the feature/bugfix branch until they and their code reviewer are satisfied with their implementation; the branch is then merged into the master branch.
