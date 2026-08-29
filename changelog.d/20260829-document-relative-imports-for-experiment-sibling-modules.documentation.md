Documented that modules sitting beside ``experiment.py`` are imported with
``from . import my_module``. Dallinger loads the experiment directory as a
package, so a plain ``import my_module`` fails in the web, worker, and clock
processes. The experiment-directory docs, troubleshooting page, and back-end
skill now describe this.
