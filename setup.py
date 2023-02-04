import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


# Because the package isn't installed yet, we have to execute version.py
# in this unusual way, reading directly from the file
# (see https://packaging.python.org/en/latest/guides/single-sourcing-package-version/).
version = {}
with open("psynet/version.py", "r") as fp:
    exec(fp.read(), version)


setuptools.setup(
    name="psynet",
    version=version["psynet_version"],
    author="Peter Harrison, Frank Höger, Pol van Rijn, Raja Marjieh, Nori Jacoby",
    author_email="pmch2@cam.ac.uk",
    description="A framework for running advanced psychological experiments.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/PsyNetDev/PsyNet",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10.0",
    include_package_data=True,
    package_data={"psynet": ["VERSION"]},
    install_requires=[
        version["dallinger_version_requirement"],
        "click",
        "datetime",
        "dominate",
        "flask",
        "importlib_resources",
        "jsonpickle",
        "pandas",
        "rpdb",
        "progress",
        "requests",
        "scipy",
        "numpy",
        "statsmodels",
        "tqdm",
        "yaspin",
        "praat-parselmouth",
        "joblib",  # Library used for internal parallelization of for loops
        "babel",  # Library used for internationalization
        "python-gettext",  # Library used for internationalization
        "sphinx==5.3.0",
    ],
    extras_require={
        "dev": [
            "awscli",
            "isort",
            "mock",
            "pre-commit",
            "pytest",
            "sphinx-autodoc-typehints",
            "furo",
        ]
    },
    entry_points={
        "console_scripts": ["psynet = psynet.command_line:psynet"],
        "pytest11": ["pytest_psynet = psynet.pytest_psynet"],
    },
)

# python3.7 setup.py sdist bdist_wheel
