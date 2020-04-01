import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dlgr_utils", # Replace with your own username
    version="0.0.9",
    author="Peter Harrison, Raja Marjieh, Nori Jacoby",
    author_email="pmc.harrison@gmail.com",
    description="Utility functions for Dallinger experiments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/computational-audition-lab/dlgr_utils",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    include_package_data=True,
    install_requires=["datetime", "flask", "dallinger", "importlib_resources", "pandas", "rpdb"]
)

# python3.7 setup.py sdist bdist_wheel
