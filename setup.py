from setuptools import setup

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    name='compass-dns-backend',
    description='Compass dynamic PowerDNS backend pipe',
    long_description=long_description,
    version='0.5.2',
    author='Lucas Barsand',
    author_email='lucas@barsand.dev',
    url='https://github.com/barsand/compass-dns-backend',
    entry_points={"console_scripts": ["compass-dns-backend = compass.dns_backend:main"]},
    license='GPLv3',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3.3',
        'Operating System :: POSIX',
        'Topic :: System :: Networking',
        'Development Status :: 3 - Alpha'
    ],
    packages=['compass'],
    install_requires=['pymongo']
)
