from setuptools import setup

setup(
    name = 'etudier',
    version = '0.0.1',
    url = 'https://github.com/edsu/etudier',
    author = 'Ed Summers',
    author_email = 'ehs@pobox.com',
    py_modules = ['etudier',],
    scripts = ['etudier.py'],
    description = 'Collect a citation graph from Google Scholar',
    install_requires = ['selenium', 'requests-html', 'networkx']
)
