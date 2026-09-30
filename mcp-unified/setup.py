from setuptools import setup, find_packages

setup(
    name="mcp-unified",
    version="1.0.0",
    description="Modular MCP Server with Unified Services",
    author="aseps",
    author_email="aseps@aseps.com",
    url="https://github.com/asepsafrudin/multiple-mcp-server-by-kimi",
    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'fastapi',
        'uvicorn',
        'psycopg2-binary',
        'pydantic',
        'ruff',
        'asyncssh',
        'google-cloud-vision',
        'google-cloud-storage',
        'google-cloud-pubsub',
        'requests',
        'httpx',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
