# Copyright 2014 Google Inc. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Setup script for OpenHTF."""

import os

from distutils.command.clean import clean
from setuptools import find_packages
from setuptools import setup


class CleanCommand(clean):
  """Custom logic for the clean command."""

  def run(self):
    clean.run(self)
    targets = [
        './dist',
        './*.egg-info',
        './openhtf/proto/*_pb2.py',
        '**/*.pyc',
        '**/*.tgz',
    ]
    os.system('rm -vrf %s' % ' '.join(targets))


requires = [    # pylint: disable=invalid-name
    'contextlib2==0.4.0',
    'enum==0.4.4',
    'Flask==0.10.1',
    'itsdangerous==0.24',
    'Jinja2==2.7.3',
    'libusb1==1.3.0',
    'M2Crypto==0.22.3',
    'MarkupSafe==0.23',
    'pyaml==15.3.1',
    'python-gflags==2.0',
    'PyYAML==3.11',
    'Rocket==1.2.4',
    'singledispatch==3.4.0.3',
    'six==1.9.0',
    'Werkzeug==0.10.4',
]


setup(
    name='openhtf',
    version='1.0',
    description='OpenHTF, the open hardware testing framework.',
    author='John Hawley',
    author_email='madsci@google.com',
    maintainer='Joe Ethier',
    maintainer_email='jethier@google.com',
    packages=find_packages(exclude='example'),
    cmdclass={
        'clean': CleanCommand,
    },
    install_requires=requires,
)
