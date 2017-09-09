from distutils.core import setup

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    name='pdyndns',
    description='PEERING testbed dynamic PowerDNS backend',
    long_description=long_description,
    version='0.3',
    author='PEERING Testbed developers',
    author_email='team@peering.usc.edu',
    url='https://github.com/PEERINGTestbed/powerdns-pdyndns-backend',
    scripts=['pdyndns.py'],
    # packages=['ripe', 'ripe.atlas', 'ripe.atlas.dyndns'],
    license='GPLv3',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3.3',
        'Operating System :: POSIX',
        'Topic :: System :: Networking',
        'Development Status :: 3 - Alpha'
    ]
)
