from setuptools import setup, find_packages
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as req_file:
    requirements = [r.strip() for r in req_file if r.strip()]


setup(
    name="FERS",
    version="0.1.41",
    author="Jeroen Hermsen",
    author_email="info@ferscloud.com",
    description="Finite Element Method library written in Rust with Python interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jeroen124/FERS_core",
    packages=find_packages(),
    include_package_data=True,
    package_data={"FERS_core": ["examples/*"]},
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Rust",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
    install_requires=requirements,
)
