# Installation

## User installation

These instructions are for if you just want to use `dlgr_utils` in an 
experiment and you don't need to run the demo or edit the source:

```
pip3 install git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils
```

Note that you must have set up your GitLab SSH keys already.

## Developer installation (RECOMMENDED)

These instructions are for if you want to run the `dlgr_utils` demo,
or if you want to edit the source:

Choose a location to put your installation, e.g. `~/cap`.

``` 
cd ~/cap
git clone 
```

This will create folder called `dlgr_utils`.
Navigate to this folder:

```
cd dlgr_utils
```

Install with pip3 (make sure you are in the appropriate virtual environment
already, e.g. by running `workon dlgr_env`):

```
pip3 install -e .
```

The `-e` flag makes it editable.

Run the demo with `dallinger debug --verbose`.

# Adding `dlgr_utils` to your Dallinger experiment

This is simply achieved by adding the following line to your `requirements.txt` file:

```
-e git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils.git#egg=dlgr_utils
```

It is wise to point to a particular commit so that your experiment doesn't 
get broken by future changes to the `dlgr_utils` package. You can do this as follows:

```
-e git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils.git@<put your commit hash here>#egg=dlgr_utils
```

e.g. 

```
-e git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils.git@6b8523d9c14198060cffa3a7f6d4c7fc5993a0a8#egg=dlgr_utils
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
