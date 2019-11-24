# Monitor

This implements a monitoring page for Dallinger experiments.

## Installation

```
pip install dlgr_monitor
```

## Usage

Suppose that you have already implemented an experiment in Dallinger,
and you wish to add a monitor route.
Open the `experiment.py` file, and import the monitor package as follows:

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
