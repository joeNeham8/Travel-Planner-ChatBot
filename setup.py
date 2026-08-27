from pathlib import Path

from setuptools import find_packages, setup


def read_requirements(path: str) -> list[str]:
    lines = Path(path).read_text().splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.startswith("#") and not line.startswith("-e")
    ]


setup(
    name="travel-intake-chatbot",
    version="0.1.0",
    author="Shaheen Nabi",
    author_email="ishaheenanbi333@gmail.com",
    packages=find_packages(),
    install_requires=read_requirements("requirements.txt"),
    python_requires=">=3.11",
)
