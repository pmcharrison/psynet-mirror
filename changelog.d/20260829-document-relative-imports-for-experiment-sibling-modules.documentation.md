Documented that modules sitting beside ``experiment.py`` are imported with
``from . import my_module``. Dallinger loads the experiment directory as a
package, so a plain ``import my_module`` fails in the web, worker, and clock
processes. PsyNet no longer puts the experiment directory on ``sys.path`` as a
workaround. Standalone power scripts still use ``python -m audit.power.core``
from the experiment root, treating ``audit/`` as a namespace package. The
experiment-directory docs, troubleshooting page, and back-end skill now
describe this.
