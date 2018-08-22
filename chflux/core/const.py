r"""
====================================
Constants (:mod:`chflux.core.const`)
====================================

.. currentmodule:: chflux.core.const

Physical constants.

====================  =========================================================
``T_0``               zero Celsius in Kelvin
``atm``               standard atmospheric pressure [Pa]
``R_gas``             molar gas constant [J mol\ :sup:`-1`\  K\ :sup:`-1`\ ]
``air_conc_stp``      air concentration at STP condition [mol m\ :sup:`-3`\ ]
====================  =========================================================
"""

__all__ = ['T_0', 'atm', 'R_gas', 'air_conc_stp']

T_0: float = 273.15
atm: float = 101325.0
R_gas: float = 8.3144598
air_conc_stp: float = atm / (R_gas * T_0)
