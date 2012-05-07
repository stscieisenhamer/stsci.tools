# Don't copy this as an example - use any other package is stsci_python,
# such as sample_package

from __future__ import division # confidence high

# This setup.py does not follow our usual pattern, because it is
# the setup for pytools -- it can't use pytools to install itself..

import sys

# We can't import this because we are not installed yet, so
# exec it instead.  We only want it to initialize itself,
# so we don't need to keep the symbol table.

syms = {}
f=open("./lib/stsci/tools/stsci_distutils_hack.py","r")
exec(f.read(), syms)
f.close()

syms['__set_svn_version__']()
syms['__set_setup_date__']()

if "version" in sys.argv :
    sys.exit(0)

from distutils.core import setup

from defsetup import setupargs, pkg

setup(
    name = 'stsci.tools',
    packages = pkg,
    **setupargs
    )
