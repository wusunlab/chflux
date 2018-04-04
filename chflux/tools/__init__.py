"""
===========================
Tools (:mod:`chflux.tools`)
===========================

.. module:: chflux.tools

This module contains miscellaneous tools to deal with data types and
dependencies.

Datetime tools
==============

Variables
---------
.. data:: chflux.tools.timestamp_parsers

   A dictionary of timestamp parsers for ``pandas.read_csv()``.

Functions
---------
.. autosummary::
   :toctree: generated/

   extract_date_substr -- Extract date substring from a list of file paths.
   parse_day_number    -- Parse day number.
   parse_unix_time     -- Parse Unix time in seconds.

Unit tools
==========
.. autosummary::
   :toctree: generated/

   parse_units -- Parse concentration and flux units from numerical values.

Miscellaneous tools
===================
.. autosummary::
   :toctree: generated/

   check_pkgreqs -- Check package requirements.
"""

from .datetimes import *
from .units import *
from .misc import *


__all__ = [s for s in dir() if not s.startswith('_')]
