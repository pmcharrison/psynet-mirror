# Adding `dlgr_utils` to your Dallinger experiment

This is simply achieved by adding the following line to your `requirements.txt` file:

```
-e git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils#egg=dlgr_utils
```

# Monitor

The `monitor` module implements a monitoring page for Dallinger experiments.

## Minimal demo of monitor

This repository includes a minimal demo of the monitor route.
You can launch this demo by running `dallinger debug --verbose` from
the top level of the repository. 
You must have already installed the `dlgr_utils` package (see instructions above).

## Adding the monitor to an experiment

Suppose that you have already implemented an experiment in Dallinger,
and you wish to add a monitor route.

Add `dlgr_utils` to your `requirements.txt` file, as described above.

Open the `experiment.py` file, and import the monitor module as follows:

``` python
import dlgr_utils.monitor
```

Now, find your experiment class, which typically will specialise 
Dallinger's built-in `Experiment` class.
Change your code so that it now specialises the monitor route's
`Experiment` class, which is found in `dlgr_utils.monitor`.
For example:

``` python
class MCMP(dlgr_utils.monitor.Experiment):
    ...
```

Add the route:

``` python
@extra_routes.route("/monitor", methods=["GET"])
def get_monitor():
    return MCMCP(db.session).render_monitor_template()
```

Now, when you run your experiment, you should be able to access the monitor
route by visiting `/monitor`.

# Running tests

```
python -m pytest
```

# Building documentation

```
make -C docs html
open docs/_build/html/index.html
```