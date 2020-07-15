import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

with open(os.path.join("psynet", 'VERSION')) as version_file:
    version = version_file.read().strip()

setuptools.setup(
    name="psynet", # Replace with your own username
    version="0.11.0",
    author="Peter Harrison, Raja Marjieh, Nori Jacoby",
    author_email="pmc.harrison@gmail.com",
    description="Utility functions for Dallinger experiments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/computational-audition-lab/psynet",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7.0',
    include_package_data=True,
    install_requires=[
        "dallinger",
        "click",
        "datetime",
        "flask",
        "importlib_resources",
        "pandas",
        "rpdb",
        "progress",
        "scipy",
        "statsmodels"
    ],
    extras_require={
        "dev": [
            "pytest",
            "mock"
        ]
    },
    entry_points={
        "console_scripts": [
            "psynet = psynet.command_line:psynet"
        ]
    }
)

# python3.7 setup.py sdist bdist_wheel
