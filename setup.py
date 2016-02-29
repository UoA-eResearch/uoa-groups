from setuptools import setup, find_packages

setup(name='uoa-groups',
      version='0.1',
      author="Markus Binsteiner",
      author_email="m.binsteiner@auckland.ac.nz",
      install_requires=[
          "argparse",
          "blist",
          "python-ldap",
          "openpyxl",
          "setuptools"
      ],
      packages=find_packages(),
      license="GLPv3",
      entry_points={
          'console_scripts': [
              'uoa-groups = uoa_groups.uoa_query:run'
          ],
      },
      description="Query UoA ldap and groups."
)
