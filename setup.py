from distutils.core import setup

setup(
    name='pdyndns',
    description='PEERING testbed dynamic PowerDNS backend',
    long_description=open('README.md', 'r').read(),
    version='0.2.2',
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
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Development Status :: 2 - Pre-Alpha'
    ]
)
