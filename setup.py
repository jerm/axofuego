from setuptools import setup, find_packages

setup(
    name="axofuego",
    version="2.0.0",
    description="Modular fire control system for live performance",
    author="kwyn",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "websockets",
        "gpiozero",
        "evdev",
        "python-dotenv",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "black",
            "flake8",
        ]
    },
    entry_points={
        "console_scripts": [
            "axofuego=main:main",
        ],
    },
)