from setuptools import setup, find_packages
# from setuptools_rust import RustExtension

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fers",
    version="0.1.0",
    author="Jeroen Hermsen",
    author_email="j.hermsen@serrac.com",
    description="Finite Element Method library written in Rust with Python interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jeroen124/fers_core",
    packages=find_packages(where="fers_core"),
    # rust_extensions=[RustExtension("fers_core.fers_core", binding="pyo3")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Rust",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        # List any Python dependencies your package has
    ],
)
