=======================
How to use this package
=======================

This package is still very much work in progress. 
We hope however that it is already useful for running
experiments within our network of collaborators.

Stability
---------

The API of this package is not permanently fixed yet;
we'd still like to be able to improve it to respond to 
feedback from users. At the same time, we want people
to be able to implement experiments using the framework
without worrying about subsequent changes to the framework
breaking their implementations. Correspondingly, we will 
try to avoid major breaking changes where possible.
Generally speaking, changes to the core API will be conducted
such that they add features without breaking back-compatibility.
Breaking changes to the API will generally be reserved for 
parts of the package that have fewest dependencies,
such as implementations of particular experiment paradigms
(e.g. MCMCP).

Extensibility
-------------

The package was designed with extensibility in mind;
in particular, we think that it should be straightforward 
to implement many new experiment interfaces and paradigms
using the tools provided here. 
If a feature doesn't exist yet, this often will just mean
that we haven't had time to implement it yet. 
If you're wondering about the feasibility of a potential new feature,
just get in touch with Peter, he'll be happy to help.

Contributing
------------

We hope that this package can expand through the contributions of
its user base. In particular, we'd welcome contributions
of new page types, new experiment paradigms, 
new demos, and updated documentation/tutorials.
Please submit such contributions as Merge Requests to the 
development branch (``dev``), and talk to Peter if you have any questions.

Feedback
--------

Any feedback about the package is of course welcome, 
just get in touch with Peter.
