import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="psynet",
    version="9.4.4",
    author="Peter Harrison, Raja Marjieh, Nori Jacoby",
    author_email="pmc.harrison@gmail.com",
    description="Utility functions for Dallinger experiments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/PsyNetDev/psynet",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    include_package_data=True,
    package_data={"psynet": ["VERSION"]},
    install_requires=[
        "dallinger>=9.4.2, <10.0.0",
        "click",
        "datetime",
        "dominate",
        "flask",
        "importlib_resources",
        "jsonpickle",
        "pandas",
        "rpdb",
        "progress",
        "scipy",
        "numpy",
        "statsmodels",
        "tqdm",
        "yaspin",
        "praat-parselmouth",
        "joblib"  # Library used for internal parallelization of for loops
    ],
    extras_require={
        "dev": [
            "isort",
            "mock",
            "pre-commit",
            "pytest",
            "sphinx-autodoc-typehints",
            "furo",
        ]
    },
    entry_points={"console_scripts": ["psynet = psynet.command_line:psynet"]},
)

# python3.7 setup.py sdist bdist_wheel
