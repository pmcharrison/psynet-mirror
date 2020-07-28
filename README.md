# Links

![Logo](logo.svg)

- [Online documentation](https://computational-audition-lab.gitlab.io/psynet/)
- [Contribution guidelines](https://gitlab.com/computational-audition-lab/computational-audition-lab/-/wikis/Computer-Resources/Tricks-for-git)

# Running tests

```
python -m pytest
```

# Building documentation locally

```
make -C docs html
open docs/_build/html/index.html
```

# Installing psynetR

pysnetR is a companion R package for preprocessing PsyNet data. It is currently 
in very early stages, with no documentation and namespace exporting not set up yet.
To install it, do the following:

```
install.packages("remotes")
remotes::install_local("path/to/psynetR/folder/within/psynet")
```

You will need to reinstall the package any time the source code changes
(i.e. the installed package will not track changes to your original PsyNet folder).

To load the package, run

```
library(psynetR)
```

To use functions within the package, you must use 3 colons, because no functions
have been exported yet. So:

```
psynetR:::import_chain_experiment(...)
```
