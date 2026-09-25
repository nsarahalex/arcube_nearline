#!/usr/bin/env python3
"""
light_dqm_funcs.py

Home for every processing/plotting function used by light_dqm_skeleton.py.
Nothing in this file should depend on argparse/args directly - functions
take plain values as arguments instead, so they can be tested and called
on their own.

Functions are originally defined in light_dqm.py

get_ptps() and adc16_to_voltage() below are already filled in, as a
worked example of exactly what "done" should look like.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from scipy.fft import rfft, rfftfreq
from scipy.stats import beta


# ----------------------------------------------------------------- #
# Config / constants                                                 #
# (copied as is from light_dqm.py)
# ----------------------------------------------------------------- #

SAMPLE_RATE = 0.016      # us per sample
adc14_max = 8191
adc14_16 = 2 ** 2        # conversion factor between 14 and 16 bit ADC
ADC_V_range = 2.0        # voltage range of the ADC
ADC_V_offset = -1.0      # voltage offset

# Channel mapping: select channels 4-15 in each group of 16
channels = []
for group_start in range(0, 64, 16):
    channels.extend(range(group_start + 4, min(group_start + 16, 64)))

# Frequency regions of interest (MHz) and window width (MHz), used by
# the noise-spectrum plots
vlist = [0.5e6, 1.8e6, 4.6e6, 7.1e6, 8.5e6, 10e6, 11.5e6, 19e6, 20e6, 25e6, 30e6]
window = 0.4e6


def load_channel_status(channel_status_file):
    """
    Load the channel-status CSV (0 = good, nonzero = bad) into a numpy array.
    Returns None if the file can't be loaded, so callers can carry on without it.
    """
    import pandas as pd
    try:
        cs_df = pd.read_csv(channel_status_file, header=None)
        return cs_df.to_numpy()
    except Exception as e:
        print(f"Could not load channel status from {channel_status_file}: {e}")
        return None


# ----------------------------------------------------------------- #
# EXAMPLE #1
# ----------------------------------------------------------------- #

def get_ptps(units, ptps16bit=500):
    """
    Get peak-to-peak thresholds for the given units.
    Args:
        units: 'ADC16', 'ADC14', or 'V'
        ptps16bit: the base threshold in 16-bit ADC counts 
    Returns:
        np.ndarray of length 8 (one threshold per ADC)
    """
    ptps_16 = np.array([ptps16bit] * 8)
    ptps_14 = ptps_16 / adc14_16
    ptps_V = ptps_16 * ADC_V_range / (adc14_max * adc14_16)

    if units == 'ADC16':
        return ptps_16
    elif units == 'ADC14':
        return ptps_14
    elif units == 'V':
        return ptps_V
    else:
        raise ValueError("Units must be 'ADC14', 'ADC16', or 'V'.")


# ----------------------------------------------------------------- #
# EXAMPLE #2              #
# ----------------------------------------------------------------- #

def adc16_to_voltage(adc_counts, mask=None):
    """Convert raw ADC16 counts to voltage."""
    if mask is not None:
        adc_counts = np.where(mask[..., np.newaxis], adc_counts, 0)
    return adc_counts * (ADC_V_range + ADC_V_offset) / (adc14_max * adc14_16)


# ----------------------------------------------------------------- #
# TODO: more variables            #
# ----------------------------------------------------------------- #

def get_waveform_info(waveform, units='ADC16', mask=None, ths=None):
    """
    Original location: light_dqm.py, "def get_waveform_info(...)"
    Returns: wvfms, noise, baseline, max_value
    """
    # TODO: paste function body from light_dqm.py here
    raise NotImplementedError("get_waveform_info not ported yet")






# ----------------------------------------------------------------- #
# TEMPLATE: use this shape for any new plot #
# ----------------------------------------------------------------- #
#
# def plot_my_new_thing(data, some_option=True, output_name='my_new_thing.pdf'):
#     """
#
#     Args:
#         data: whatever array(s) this needs (pass them in explicitly -
#                don't reach for a global variable)
#         some_option: any tunable knob, with a sensible default
#         output_name: filename only (no folder) - the caller decides
#                      the directory, same as every other plot function here
#     """
#     fig, ax = plt.subplots(figsize=(10, 4))
#     # ... draw the plot on `ax` using matplotlib ...
#     plt.tight_layout()
#
#     # every plot in this codebase saves into args.tmp_dir, one PDF page
#     # per plot; light_dqm_skeleton.py merges them all together at the end
#     output_pdf = output_name  # skeleton passes tmp_dir/output_name already
#     with PdfPages(output_pdf) as pdf:
#         pdf.savefig(fig)
#         plt.close(fig)
#
# Then, to actually use it:
#   1. Import it at the top of light_dqm_skeleton.py's import block.
#   2. Add a `try/except` block for it inside run_processing(), following
#      the same shape as the existing ones
#   3. To trackin Grafana add a line like
#      metrics["my_new_metric_name"] = ... inside that same try block.
