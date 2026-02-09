# PyCharm References in PsyNet Documentation

## Summary

This document tabulates all references to PyCharm in the PsyNet documentation.

## Main Documentation (docs/)

| File | Section/Context | Type | Reference |
|------|----------------|------|-----------|
| `docs/learning/how_to_learn.rst` | Opening PsyNet repository | Recommendation | "Open the resulting folder (`~/PsyNet`) in your IDE (we normally recommend PyCharm)." |
| `docs/learning/how_to_learn.rst` | Running demos | Instruction | "In your PyCharm terminal, you can navigate to a particular demo..." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 2: Install PyCharm | Recommendation | "We recommend using PyCharm as your integrated development environment (IDE) for working with PsyNet." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 2: Install PyCharm | Requirement | "For proper integration with PsyNet (especially if you are using the Docker installation route), you will need to use the Professional version in particular." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 2: Install PyCharm | Windows configuration | Instructions for configuring PyCharm to use Unix-style line endings (LF) on Windows |
| `docs/installation/docker_installation/shared_installation.rst` | Step 2: Install PyCharm | Settings reference | "Open PyCharm's settings." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 5: Set up PyCharm | Initial setup | "The first time you open PyCharm you may need to enter some license information..." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 5: Set up PyCharm | Opening project | "Now, within PyCharm, click File > Open and open the folder that Git downloaded for you. This opens the experiment directory as a PyCharm 'project'." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 5: Set up PyCharm | Building experiment | "You build the experiment by running the following in your PyCharm terminal:" |
| `docs/installation/docker_installation/shared_installation.rst` | Step 5: Set up PyCharm | Docker integration | "Now you should configure PyCharm to use your experiment's Docker image." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 5: Set up PyCharm | Professional Edition requirement | "If you are not using PyCharm Professional Edition, you will probably not have the option to integrate PyCharm with Docker in this way." |
| `docs/installation/docker_installation/shared_installation.rst` | Step 6: Running the experiment | Running commands | "Try this by running the following command in your PyCharm terminal:" |
| `docs/installation/docker_installation/windows_installation.rst` | Troubleshooting | Reference | "setting up Git and PyCharm in Windows." |
| `docs/installation/virtual_environment_installation/windows.rst` | Development options | Option | "You can develop on Windows (for example, PyCharm on Windows using a WSL interpreter), or install a Linux IDE inside WSL." |
| `docs/installation/virtual_environment_installation/windows.rst` | Installing IDE in WSL | Installation command | "sudo snap install pycharm-educational --classic" |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Opening project | Instruction | "To open a project in PyCharm (e.g. a demo), click 'Open' in the PyCharm welcome screen..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Opening project | Alternative method | "Alternatively, if you already have a PyCharm project open, click 'File' > 'Open'..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Virtual environment setup | Dialogue box | "When you open a new project in PyCharm, you should see a dialogue box..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Virtual environment setup | PyCharm behavior | "PyCharm remembers which virtual environment to use for each project, and will load it automatically..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Virtual environment setup | Alternative method | "If you do not see this PyCharm dialogue box, you can instead create the virtual environment by..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Virtual environment setup | Processing | "then press OK. PyCharm will spend some time processing this selection..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Virtual environment activation | Terminal | "If you have only just created your new virtual environment in PyCharm, you might need to open a new terminal tab..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Virtual environment activation | Automatic activation | "Your virtual environment should activate automatically when you open your project in PyCharm..." |
| `docs/installation/virtual_environment_installation/opening_a_project_in_a_virtual_environment.rst` | Completion | Final step | "Once PyCharm has finished installing the required packages, you should be able to run the experiment" |
| `docs/installation/additional_developer_installation.rst` | Opening PsyNet project | Instruction | "Open PsyNet as a PyCharm project" |
| `docs/installation/additional_developer_installation.rst` | Opening PsyNet project | Steps | "If you are using PyCharm, you can open the PsyNet project by selecting 'Open' from the PyCharm welcome screen..." |
| `docs/installation/additional_developer_installation.rst` | Opening PsyNet project | Virtual environment | "Follow the PyCharm prompts to create a virtual environment for PsyNet." |
| `docs/experiment_development/development_workflow.rst` | PyCharm as an IDE | Recommendation | "We particularly recommend PyCharm Professional, which integrates well with the development requirements of PsyNet." |
| `docs/experiment_development/development_workflow.rst` | PyCharm as an IDE | Educational license | "It is possible to get free educational licenses for PyCharm Professional, see online for details." |
| `docs/experiment_development/development_workflow.rst` | PyCharm as an IDE | Configuration | "PsyNet demos come with instructions about how to configure your PyCharm IDE." |
| `docs/experiment_development/development_workflow.rst` | PyCharm as an IDE | Setup steps | "The most important steps are (a) opening the experiment directory as a project (File > Open in PyCharm), and (b) configuring your Python interpreter." |
| `docs/experiment_development/development_workflow.rst` | PyCharm as an IDE | File navigation | "Once you've set up your PyCharm interpreter, you will be able to see your experiment's source files..." |
| `docs/experiment_development/development_workflow.rst` | Commenting code | Shortcut | "There is a useful PyCharm shortcut for this, CMD-/." |
| `docs/experiment_development/development_workflow.rst` | Running tests | PyCharm users note | "PyCharm users: At the time of writing (June 2024) there is a bug in PyCharm's test result parser..." |
| `docs/developer/running_tests.rst` | Running tests | Preference | "If you are using PyCharm it is usually preferable to run the tests through the PyCharm interface." |
| `docs/developer/running_tests.rst` | Running tests | Configuration | "First you have to configure PyCharm's run configurations." |
| `docs/developer/running_tests.rst` | Running tests | Running tests | "Now you can right click on a particular test file or test function within PyCharm and run the test..." |
| `docs/tutorials/creating_a_new_experiment.rst` | Opening directory | Instruction | "The first step is then to open this directory in PyCharm" |
| `docs/tutorials/creating_a_new_experiment.rst` | Package installation | Automatic | "Assuming you have internet access, PyCharm should then automatically download and install the required packages..." |
| `docs/tutorials/creating_a_new_experiment.rst` | Terminal | Verification | "If you then open a new terminal window in PyCharm, you should see `(<your-project-name)`" |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Git GUI | Recommendation | "We therefore recommend taking advantage of the Git GUI in your IDE. Most IDEs do provide some kind of Git GUI. Here we're going to provide some screenshots from the Git GUI in PyCharm, the recommended IDE for PsyNet..." |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Git GUI | Opening project | "When using the PyCharm Git GUI we typically open a PyCharm 'project' corresponding to the Git repository." |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Git GUI | Opening GUI | "Suppose we have been working on our code in PyCharm. We can open PyCharm's Git GUI by clicking the 'Commit' tab..." |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Merge conflicts | Easier method | "However, it is much easier to work instead with the Git GUI in (e.g. PyCharm)." |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Merge conflicts | Interface | "use the '>>' button in the PyCharm interface" |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Staging commits | Method | "Staging commits using the PyCharm GUI" |
| `docs/tutorials/version_control_with_git/experiment_implementation_workflow.rst` | Alternative IDEs | Note | "In particular, a recommended free alternative to PyCharm is VSCode." |
| `docs/tutorials/version_control_with_git/essential_concepts.rst` | Diff visualization | Example | "Additionally, many IDEs (e.g. PyCharm) provide similar diff visualizations." |
| `docs/tutorials/unity_integration.rst` | Unity debugging | Comparison | "Rider (https://www.jetbrains.com/rider/) is very similar to PyCharm, and it is free for academic usage." |
| `docs/demos/introduction.rst` | Learning PsyNet | Alternative method | "An alternative way to learn more about PsyNet functions or classes is via PyCharm. Open the demo directory in PyCharm..." |
| `docs/demos/introduction.rst` | Learning PsyNet | Exploring code | "open the repository in PyCharm, and then look around for an object you want to learn more about" |
| `docs/learning/tracks/music_perception.rst` | Opening demo | Instruction | "Open the demo as a new PyCharm project." |

## Test Experiment Documentation (tests/experiments/*/docs/)

| File Pattern | Section/Context | Type | Reference |
|--------------|----------------|------|-----------|
| `tests/experiments/*/docs/INSTALL.md` | Prerequisites | Optional requirement | "- PyCharm (optional)" |
| `tests/experiments/*/docs/INSTALL.md` | Installing PyCharm | Recommendation | "We recommend using PyCharm for PsyNet experiments, specifically the Professional Edition." |
| `tests/experiments/*/docs/INSTALL.md` | Installing PyCharm | Download link | "Download PyCharm from [this link](https://www.jetbrains.com/help/pycharm/installation-guide.html)." |
| `tests/experiments/*/docs/INSTALL.md` | Installing PyCharm | Windows configuration | "*Windows users only*: You should configure PyCharm to use Unix-style line endings (LF)..." |
| `tests/experiments/*/docs/INSTALL.md` | Installing PyCharm | Settings reference | "Open PyCharm's settings." |
| `tests/experiments/*/docs/INSTALL.md` | Setting up PyCharm | Initial setup | "The first time you open PyCharm you may need to enter some license information..." |
| `tests/experiments/*/docs/INSTALL.md` | Setting up PyCharm | Opening project | "Now, within PyCharm, click File > Open and open the folder that Git downloaded for you. This opens the experiment directory as a PyCharm 'project'." |
| `tests/experiments/*/docs/INSTALL.md` | Setting up PyCharm | Building experiment | "You build the experiment by running the following in your PyCharm terminal:" |
| `tests/experiments/*/docs/INSTALL.md` | Setting up PyCharm | Docker integration | "Now you should configure PyCharm to use your experiment's Docker image." |
| `tests/experiments/*/docs/INSTALL.md` | Setting up PyCharm | Running commands | "Try this by running the following command in your PyCharm terminal:" |
| `tests/experiments/*/docs/INSTALL.md` | Troubleshooting | Reference | "setting up Git and PyCharm in Windows." |
| `tests/experiments/*/docs/RUN.md` | Remote debugging | Feature | "You can use PyCharm's remote debugger within this Docker-based PsyNet environment." |
| `tests/experiments/*/docs/RUN.md` | Remote debugging | Configuration | "1. Click Run > Edit Configurations in PyCharm." |
| `tests/experiments/*/docs/RUN.md` | Remote debugging | Starting debugger | "Now start this debug server via your PyCharm interface (this typically involves clicking on a green bug icon)." |
| `tests/experiments/*/docs/RUN.md` | Remote debugging | Code import | "import pydevd_pycharm" |
| `tests/experiments/*/docs/RUN.md` | Remote debugging | Activation | "If all goes well, the PyCharm interpreter should activate once it reaches this code," |

## Dockerfiles

| File Pattern | Context | Type | Reference |
|--------------|---------|------|-----------|
| `tests/experiments/*/Dockerfile` | Comment | Purpose | "# This is used for debugging experiments using PyCharm" |
| `tests/experiments/*/Dockerfile` | Package installation | Dependency | "RUN python3 -m pip install pydevd-pycharm~=221.6008.17" |

## Statistics

- **Total unique files with PyCharm references**: ~50+ files
- **Main documentation files**: 15 files
- **Test experiment documentation files**: ~35 files (multiple experiments with INSTALL.md and RUN.md)
- **Dockerfiles**: ~10 files

## Categories of References

1. **Recommendations**: PyCharm is recommended as the IDE for PsyNet development
2. **Installation instructions**: How to install and configure PyCharm
3. **Setup instructions**: How to set up PyCharm for PsyNet projects
4. **Usage instructions**: How to use PyCharm features (terminal, debugger, Git GUI, etc.)
5. **Configuration**: Specific PyCharm settings (line endings, interpreters, run configurations)
6. **Troubleshooting**: References in troubleshooting sections
7. **Dependencies**: Package installations for PyCharm integration (pydevd-pycharm)
