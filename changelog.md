# Change Log

# current

- Refined saturation vapor pressure and dew temperature functions.
- List of physical constants moved from `config.yaml` to `common_func.py`.
- Added some summary statistics functions in `common_func.py`:
	* `resist_mean()`: outlier-resistant mean
	* `resist_std()`: outlier-resistant standard deviation
	* `IQR_func()`: interquartile range

@TODO:
- Test and refine the chamber schedule function.
- Add flow data parsing
- Add leaf area auxiliary data parsing

# 0.1.1 (2017-01-18)

- Added a new chamber lookup table function controlled by external config file `chamber.yaml`.
- Bug fix in chamber schedule.
- Added flow data settings to the config.
- Use `dict.update()` method for user custom config.
- Variable fix: standard error of flux estimate, `sd_flux_*` --> `se_flux_*`.

# 0.1.0 (2017-01-07)

- Main program reorganized into functions.
- Configuration file generated.
- Reformatted to comply with PEP8 standard.
- Bug fix: year number in `flux_calc.flux_calc()`.
- Added a procedure to generate curve fitting plots.

# 0.0.1 (2016-07-18)

- Created by Wu Sun @ UCLA (wu.sun@ucla.edu).