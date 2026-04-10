import os
from pathlib import Path
from setuptools import setup, find_packages

setup(
    name=os.getenv("NAME", "mcp-unified-advanced-features" if not os.getenv("CI") else "DUMMY"),
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'openai>=1.0.0',
        'asyncio>=3.0.0',
        'aiofiles>=0.9.0',
        'networkx>=3.0.0',
        'python-dotenv>=1.0.0',
        'psutil>=5.8.0',
        'requests>=2.28.0',
        'pyyaml>=6.0.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'black>=22.0.0',
            'flake8>=4.0.0',
            'mypy>=0.991',
            'bandit>=1.7.0',
            'safety>=2.3.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'advanced-features=mcp_unified.core.advanced_features.cli:main',
        ],
    },
    author='MCP Unified Team',
    author_email='mcp-unified@example.com',
    description='Advanced features for MCP Unified including performance optimization, advanced AI, and security audit',
    long_description=Path('README.md').read_text() if Path('README.md').exists() else '',
    long_description_content_type='text/markdown',
    url='https://github.com/mcp-unified',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    python_requires='>=3.8',
    license='MIT',
)