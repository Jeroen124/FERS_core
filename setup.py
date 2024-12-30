from setuptools import setup, find_packages, Command
import platform
import subprocess
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as req_file:
    requirements = [r.strip() for r in req_file if r.strip()]

platform_system = platform.system().lower()  # 'windows', 'linux', 'darwin'
platform_machine = platform.machine().lower()  # 'x86_64', 'amd64', 'aarch64', etc.

# Normalize 'arm64' to 'aarch64' for compatibility
if platform_machine == "arm64":
    platform_machine = "aarch64"

# Map platforms to prebuilt wheels
wheel_dir = os.path.join(os.path.dirname(__file__), "wheels")
wheels = {
    ("windows", "amd64"): "fers_calculations-0.1.0-cp312-cp312-win_amd64.whl",
    ("linux", "x86_64"): "fers_calculations-0.1.0-cp312-cp312-manylinux_2_34_x86_64.whl",
    ("darwin", "x86_64"): "fers_calculations-0.1.0-cp312-cp312-macosx_10_12_x86_64.whl",
}

wheel_file = wheels.get((platform_system, platform_machine), "")


# Post-install script to install the correct wheel
def install_wheel():
    if wheel_file and os.path.exists(os.path.join(wheel_dir, wheel_file)):
        print(f"Installing prebuilt wheel: {wheel_file}")
        subprocess.run(["pip", "install", os.path.join(wheel_dir, wheel_file)], check=True)
    else:
        raise RuntimeError(
            f"No compatible wheel found for platform {platform_system} on {platform_machine}. "
            "Ensure the correct wheel is included in the package."
        )


# Custom install command
class CustomInstallCommand(Command):
    description = "Custom install command to handle prebuilt wheel installation"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        install_wheel()


setup(
    name="FERS",
    version="0.1.2",
    author="Jeroen Hermsen",
    author_email="j.hermsen@serrac.com",
    description="Finite Element Method library written in Rust with Python interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jeroen124/FERS_core",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Rust",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    data_files=[("wheels", [os.path.join(wheel_dir, f) for f in os.listdir(wheel_dir)])],
    cmdclass={
        "install": CustomInstallCommand,
    },
)
