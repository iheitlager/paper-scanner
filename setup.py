#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='paper_scanner',
    version="0.1",
    description='LLM Paper analysis',
    long_description=long_description,
    license='MIT',
    author='Ilja Heitlager',
    # author_email='',
    maintainer='Ilja Heitlager',
    maintainer_email='iheitlager@schubergphilis.com',
    keywords=["research-tools"],
    url='https://github.com/iheitlager/paper-scanner',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    test_suite="tests",
    platforms=["any"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.11",
        "Intended Audience :: Researchers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English"
    ],
    install_requires=[],
    zip_safe=True,
)