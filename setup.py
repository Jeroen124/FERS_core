from setuptools import setup, find_packages, Command
import os
import platform
import subprocess

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as req_file:
    requirements = req_file.readlines()
    requirements = [r.strip() for r in requirements if r.strip()]


platform_system = platform.system().lower()  # 'windows', 'linux', 'darwin'
platform_machine = platform.machine().lower()  # 'x86_64', 'amd64', 'aarch64', etc.

# Normalize 'arm64' to 'aarch64' for compatibility
if platform_machine == "arm64":
    platform_machine = "aarch64"

wheel_dir = "wheels"
wheels = {
    ("windows", "amd64"): "fers_calculations-0.1.0-cp310-cp310-win_amd64.whl",
    ("linux", "aarch64"): "fers_calculations-0.1.0-cp310-cp310-manylinux_2_34_aarch64.whl",
    ("linux", "x86_64"): "fers_calculations-0.1.0-cp310-cp310-manylinux_2_34_x86_64.whl",
}

wheel_file = wheels.get((platform_system, platform_machine), "")
data_files = []
if wheel_file and os.path.exists(os.path.join(wheel_dir, wheel_file)):
    data_files.append((wheel_dir, [os.path.join(wheel_dir, wheel_file)]))


class InstallCommand(Command):
    """Custom install command to handle the wheel installation"""

    def run(self):
        if wheel_file and os.path.exists(os.path.join(wheel_dir, wheel_file)):
            print(f"Installing {wheel_file} for {platform_system} on {platform_machine}")
            subprocess.run(["pip", "install", os.path.join(wheel_dir, wheel_file)])
        else:
            print("No compatible precompiled wheel found for this platform.")


setup(
    name="FERS",
    version="0.1.2",
    author="Jeroen Hermsen",
    author_email="j.hermsen@serrac.com",
    description="Finite Element Method library written in Rust with Python interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jeroen124/FERS_core",
    packages=find_packages(where="FERS_core"),
    # rust_extensions=[RustExtension("FERS_core.FERS_core", binding="pyo3")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Rust",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,  # Read requirements from requirements.txt
    data_files=data_files,  # Include the prebuilt wheels in the package
    cmdclass={
        "install": InstallCommand,  # Use the custom install command
    },
)
