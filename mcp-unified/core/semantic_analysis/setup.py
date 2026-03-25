from setuptools import setup, find_packages

setup(
    name='mcp-unified-semantic-analysis',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
'astroid>=2.11.0',
        'ruff>=0.1.0',
        'mypy>=1.5.0',
        'rope>=0.20.0',
        'jedi>=0.18.0',
        'python-jsonrpc-server>=0.4.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
            'black>=22.0.0',
            'flake8>=4.0.0',
            'mypy>=0.991',
        ],
    },
    entry_points={
        'console_scripts': [
            'semantic-analyzer=mcp_unified.core.semantic_analysis.cli:main',
        ],
    },
    author='MCP Unified Team',
    author_email='mcp-unified@example.com',
    description='Semantic code analysis tools for MCP Unified',
    long_description=open('README.md').read(),
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