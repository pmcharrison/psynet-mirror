**Batch Automation for Massive Deployments**
============================================

When running multiple experiment variants across different
servers, locales, or conditions, manually repeating the provisioning,
deployment, and destruction steps is highly time-consuming and prone to
errors. The following scripts provide a framework to automate and
parallelize these processes, making massive deployments manageable.

Example Python scripts:

-  **Provisioning:** The batch_provision.py script automatically
      creates multiple EC2 instances (servers) across different AWS
      regions in parallel.

-  **Deployment:** The batch_deploy.py script iterates through a
      list of configurations, dynamically generating a unique config.py
      for each variant before deploying it to a specific server. This
      ensures every experiment is launched with consistent, correct
      parameters.

-  **Destroying:** The batch_destroy.py script allows for the
      quick and safe termination of multiple deployed applications
      across a host.

**Important: Adaptation is Required!**

These files are **only examples** and are designed to be adapted
to your specific experiment. You must edit the core configuration
variables found within each Python file before running them. Please
check each file for details.

These example scripts can be found and downloaded from the repo
cococo-shared-files <https://gitlab.com/cococo-shared/cococo-shared-files/-/tree/master/deployment/massive_deployment?ref_type=heads>`__.`
