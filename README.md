# Monitor

This implements a monitoring page for Dallinger experiments.

## Installation

```
pip install git+ssh://git@gitlab.com/computational-audition-lab/dlgr-monitor
```

Note that you must have set up your GitLab SSH keys already.

## Usage

Suppose that you have already implemented an experiment in Dallinger,
and you wish to add a monitor route.

In a normal project, you could add `dlgr-monitor` to the required dependencies
by adding the following line to your `requirements.txt` file:

```
git+ssh://git@gitlab.com/computational-audition-lab/dlgr-monitor
```

Then running `pip install -r requirements.txt` would automatically install
all dependencies, including `dlgr_monitor`.
However, Dallinger also looks at `requirements.txt`, and currently fails to parse
these references to Git repositories. So, for now it seems necessary to specify
the dependency as if it were a PyPi package:

```
dlgr_monitor
```

and just make sure you install the package manually using

```
pip install git+ssh://git@gitlab.com/computational-audition-lab/dlgr-monitor
```

Now, open the `experiment.py` file, and import the monitor package as follows:

``` python
import dlgr_monitor.main
```

Now, find your experiment class, which typically will specialise 
Dallinger's built-in `Experiment` class.
Change your code so that it now specialises the monitor route's
`Experiment` class, which is found in `dlgr_monitor.main`.
For example:

``` python
class MCMP(dlgr_monitor.main.Experiment):
    ...
```

Now, when you run your experiment, you should be able to access the monitor
route by visiting `/monitor`.
