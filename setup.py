import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dlgr_monitor", # Replace with your own username
    version="0.0.1",
    author="Peter Harrison, Nori Jacoby",
    author_email="pmc.harrison@gmail.com",
    description="Implementing a monitor route for Dallinger experiments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/computational-audition-lab/dlgr_monitor",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    include_package_data=True,
    install_requires=["datetime", "flask", "dallinger", "importlib.resources"]
)

# python3.7 setup.py sdist bdist_wheel
