from glob import glob
from setuptools import find_packages, setup

package_name = "patrol_navigation"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="cwjeong",
    maintainer_email="cwjeong@example.com",
    description="ROS 2 mapping bridge and launch files for the AI patrol robot.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "map_bridge = patrol_navigation.map_bridge:main",
        ],
    },
)
