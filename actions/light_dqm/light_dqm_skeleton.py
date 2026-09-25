#!/usr/bin/env python3
##########################################
##                                      ##
## ~ Light DQM - skeleton~              ##
##                                      ##
##########################################
##
## This is a restructured SKELETON of light_dqm.py. It keeps:
##   - the CLI / config
##   - the per-file metadata block (orig. lines ~1217-1325)
##   - the try/except-per-plot / placeholder-PDF pattern
##   - the "merge everything in tmp_dir into one PDF" step
##   - a new metrics dict that gets fed to Grafana
##
## NOT reimplementing any of the physics/plotting
## functions (get_waveform_info, get_fprompt_estimate, get_noise_spectra,
## check_baseline, plot_*, etc). Those should be copied verbatim from
## light_dqm.py into light_dqm_funcs.py
###########################################

import os
import sys
import time
import glob
import json
import argparse
import traceback

import numpy as np
import pandas as pd
import h5py

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PyPDF2 import PdfMerger
from PIL import Image

try:
    from light_dqm_funcs import (
        get_ptps, adc16_to_voltage, get_waveform_info, get_max_value_mask,
        tag_large_events, get_fprompt_estimate, get_noise_spectra,
        check_flatline, check_baseline,
        plot_sum_waveform, plot_fprompt_rates, plot_fprompt_occurrences,
        plot_noises, plot_baselines, plot_flatline_mask, plot_baseline_mask,
        plot_noise_spectra_epcb,
        save_as_json, read_from_json, placeholder_pdf,
    )
except ImportError as e:
    print(f"[skeleton] light_dqm_funcs not found/incomplete ({e}); "
          f"falling back to NotImplementedError stubs.")

    def _stub(name):
        def _f(*a, **k):
            raise NotImplementedError(
                f"'{name}' has not been ported from light_dqm.py yet"
            )
        return _f

    get_ptps = _stub("get_ptps")
    adc16_to_voltage = _stub("adc16_to_voltage")
    get_waveform_info = _stub("get_waveform_info")
    get_max_value_mask = _stub("get_max_value_mask")
    tag_large_events = _stub("tag_large_events")
    get_fprompt_estimate = _stub("get_fprompt_estimate")
    get_noise_spectra = _stub("get_noise_spectra")
    check_flatline = _stub("check_flatline")
    check_baseline = _stub("check_baseline")
    plot_sum_waveform = _stub("plot_sum_waveform")
    plot_fprompt_rates = _stub("plot_fprompt_rates")
    plot_fprompt_occurrences = _stub("plot_fprompt_occurrences")
    plot_noises = _stub("plot_noises")
    plot_baselines = _stub("plot_baselines")
    plot_flatline_mask = _stub("plot_flatline_mask")
    plot_baseline_mask = _stub("plot_baseline_mask")
    plot_noise_spectra_epcb = _stub("plot_noise_spectra_epcb")
    save_as_json = _stub("save_as_json")
    read_from_json = lambda *a, **k: None
    placeholder_pdf = _stub("placeholder_pdf")


def _lazy_import_grafana():
    from grafana_metrics import push_metrics
    return push_metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Process and plot DUNE light file data.")
    parser.add_argument('--input_path', type=str, default='.', help='Path to input file')
    parser.add_argument('--file_syntax', type=str, default='.', help='File name syntax')
    parser.add_argument('--channel_status_file', type=str,
                         default='light_dqm/channel_status.csv', help='Channel status file')
    parser.add_argument('--output_dir', type=str, default='dqm_plots/', help='Final output dir')
    parser.add_argument('--tmp_dir', type=str, default='tmp/', help='Scratch dir for per-plot files')
    parser.add_argument('--units', type=str, default='ADC16', choices=['ADC16', 'ADC14', 'V'])
    parser.add_argument('--ptps16bit', type=int, default=500)
    parser.add_argument('--start_run', type=int, default=0)
    parser.add_argument('--nfiles', type=int, default=1)
    parser.add_argument('--ncomp', type=int, default=-1)
    parser.add_argument('--powspec_nevts', type=int, default=500)
    parser.add_argument('--max_evts', type=int, default=500)
    parser.add_argument('--write_json_blobs', type=bool, default=False)
    #new ones
    parser.add_argument('--push_grafana', action='store_true',
                         help='Push the metrics dict to InfluxDB/Grafana at the end of each file')
    parser.add_argument('--grafana_run_tag', type=str, default=None,
                         help='Value for the "run" tag sent with each metric (defaults to i_file)')
    parser.add_argument('--metrics_json_out', type=str, default=None,
                         help='If set, also dump the metrics dict to this path as JSON')
    return parser.parse_args()


MIN_GB_PER_FILE = 1


def build_file_metadata(file, filename, args, ptps):
    size_bytes = os.path.getsize(filename)
    size_gb = size_bytes / (1024 ** 3)
    MULT = max(1, int(size_gb // MIN_GB_PER_FILE))

    start_timestamp = file["light/events/data"][0]['utime_ms'][0]
    end_timestamp = file["light/events/data"][-1]['utime_ms'][0]
    start_central = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_timestamp / 1000 - 6 * 3600))
    end_central = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(end_timestamp / 1000 - 6 * 3600))

    beam_mask = (file['light/events/data']['trig_type'] == 1)
    timestamps = file['light/events/data']['tai_ns'][:, 0]
    file_length = (np.max(timestamps) - np.min(timestamps)) / 1e9
    time_differences = timestamps[1:] - timestamps[:-1]

    beam_trigger_rate = np.sum(beam_mask) / file_length
    self_trigger_rate = np.sum(beam_mask == 0) / file_length
    smallest_time_diff = np.min(time_differences / 1e3)

    nevents_total = file["light/wvfm/data"]['samples'][::MULT, :, :, :].shape[0]
    sel_idx = np.linspace(0, nevents_total - 1, nevents_total, dtype=int)

    wvfms, noises, baselines, max_values = get_waveform_info(
        file["light/wvfm/data"]['samples'][::MULT, :, :, :], args.units, mask=sel_idx, ths=ptps
    )

    return dict(
        MULT=MULT,
        start_central=start_central,
        end_central=end_central,
        file_length=file_length,
        beam_trigger_rate=beam_trigger_rate,
        self_trigger_rate=self_trigger_rate,
        smallest_time_diff=smallest_time_diff,
        wvfms=wvfms,
        noises=noises,
        baselines=baselines,
        max_values=max_values,
    )


def run_processing(meta, args, i_file, ncomps, cs, tmp_dir):
    metrics = {}
    wvfms, noises, baselines, max_values = (
        meta["wvfms"], meta["noises"], meta["baselines"], meta["max_values"]
    )

    metrics["beam_trigger_rate_hz"] = round(float(meta["beam_trigger_rate"]), 3)
    metrics["self_trigger_rate_hz"] = round(float(meta["self_trigger_rate"]), 3)
    metrics["min_dead_time_us"] = round(float(meta["smallest_time_diff"]), 3)
    metrics["file_length_s"] = round(float(meta["file_length"]), 3)
    metrics["n_events"] = int(wvfms.shape[0])

    try:
        large_event_array = tag_large_events(
            WVFM_ARRAY=(wvfms - baselines[:, :, :, np.newaxis]),
            ADC_LIST=None, TICKS=wvfms.shape[-1],
        )
        plot_sum_waveform(large_event_array, args.units, output_name='plot1_sumwvfm.pdf')
    except Exception:
        placeholder_pdf(tmp_dir, 'plot1_sumwvfm.pdf', "Failed to plot summed waveforms")
        traceback.print_exc()
    #HV Instability plots
    try:
        low_fprompt_array = get_fprompt_estimate(
            WVFM_ARRAY=(wvfms - baselines[:, :, :, np.newaxis]) / 4,
            ARRIVAL_TICK=77, THRESHOLD=600,
        )
        fprompt_rate_per_adc = np.round(
            (low_fprompt_array.sum(axis=0) * meta["MULT"]) / meta["file_length"], 2
        )
        for i_adc, rate in enumerate(np.atleast_1d(fprompt_rate_per_adc).ravel()):
            metrics[f"hv_instability_rate_adc{i_adc}_hz"] = float(rate)
        metrics["hv_instability_rate_max_hz"] = float(np.max(fprompt_rate_per_adc))

        plot_fprompt_rates(
            HVINST_ARRAY=low_fprompt_array, FPROMPT_THD=20,
            FILE_LENGTH=round(meta["file_length"], 2), MULT=meta["MULT"],
            output_name='plot6_hv_instabilities.pdf',
        )
        plot_fprompt_occurrences(
            HVINST_ARRAY=low_fprompt_array, FILE_LENGTH=round(meta["file_length"], 2),
            output_name='plot7_hv_instabilities.pdf',
        )
    except Exception:
        placeholder_pdf(tmp_dir, 'plot6_hv_instabilities.pdf', "Failed to compute HV instability rate")
        traceback.print_exc()
    #Noise power spectrum
    if args.powspec_nevts > 0:
        try:
            wvfms_v = adc16_to_voltage(wvfms[:args.powspec_nevts])
            freq_bins, noise_spectra, noise_spectrum, upper, lower = get_noise_spectra(wvfms_v)
            plot_noise_spectra_epcb(
                freq_bins, noise_spectrum, None, None,
                skip_bad_channels=True, nevts=len(wvfms_v),
                output_name='plot5_powspec.pdf',
            )
            del wvfms_v
        except Exception:
            placeholder_pdf(tmp_dir, 'plot5_powspec.pdf', "Failed to plot noise spectra")
            traceback.print_exc()
    #Noise trend vs history
    prev_noises = None
    try:
        prev_noises = read_from_json(ncomps, args.output_dir, 'noises.json')
        noise_c, noise_l, noise_u = plot_noises(
            prev_noises, noises, i_evt=np.arange(baselines.shape[0]),
            mask_inactive=False, output_name='plot4_noises.pdf',
        )
        metrics["mean_noise_adc_counts"] = round(float(np.nanmean(noise_c)), 3)
        if args.write_json_blobs:
            save_as_json(i_file, noise_c, noise_l, noise_u, args.output_dir, 'noises.json')
    except Exception:
        placeholder_pdf(tmp_dir, 'plot4_noises.pdf', "Failed to plot noises")
        traceback.print_exc()
    #Baseline trend vs history
    bline_c = bline_l = bline_u = None
    prev_baselines = None
    try:
        prev_baselines = read_from_json(ncomps, args.output_dir, 'baselines.json')
        bline_c, bline_l, bline_u = plot_baselines(
            prev_baselines, baselines, i_evt=np.arange(baselines.shape[0]),
            mask_inactive=False, output_name='plot2_baselines.pdf',
        )
        metrics["mean_baseline_adc_counts"] = round(float(np.nanmean(bline_c)), 3)
        if args.write_json_blobs:
            save_as_json(i_file, bline_c, bline_l, bline_u, args.output_dir, 'baselines.json')
    except Exception:
        placeholder_pdf(tmp_dir, 'plot2_baselines.pdf', "Failed to plot baselines")
        traceback.print_exc()
    #Flatlined channels
    try:
        flatlined = check_flatline(max_values, threshold=3e2)
        metrics["frac_channels_flatlined"] = round(float(np.mean(flatlined)), 4)
        plot_flatline_mask(
            flatlined, cs, output_name=os.path.join(tmp_dir, 'plot0_flatline.pdf'),
            times=(meta["start_central"], meta["end_central"]), grafana=False,
        )
    except Exception:
        placeholder_pdf(tmp_dir, 'plot0_flatline.pdf', "Failed to plot flatlined channels")
        traceback.print_exc()
    #Baseline deviation check
    try:
        if bline_c is not None:
            baselined, status = check_baseline(
                prev_baselines, (bline_c, bline_l, bline_u), units=args.units, threshold=900,
            )
            metrics["frac_channels_baseline_deviating"] = round(float(np.mean(baselined)), 4)
            plot_baseline_mask(
                baselined, cs, output_name=os.path.join(tmp_dir, 'plot0_baseline.pdf'),
                times=(meta["start_central"], meta["end_central"]), grafana=False,
            )
    except Exception:
        placeholder_pdf(tmp_dir, 'plot0_baseline.pdf', "Failed to plot baseline fluctuations")
        traceback.print_exc()

    return metrics


def build_report_pdf(tmp_dir, output_dir, short_filename, header_lines):
    merger = PdfMerger()

    header_pdf = os.path.join(tmp_dir, "_header.pdf")
    with PdfPages(header_pdf) as pdf:
        fig, ax = plt.subplots(figsize=(16, 6))
        ax.axis('off')
        ax.text(0.01, 0.99, "\n".join(header_lines), va='top', ha='left',
                 fontsize=12, family='monospace')
        pdf.savefig(fig)
        plt.close(fig)
    merger.append(header_pdf)
    os.remove(header_pdf)

    for png_path in sorted(glob.glob(os.path.join(tmp_dir, "*.png"))):
        png_as_pdf = png_path[:-4] + ".pdf"
        Image.open(png_path).convert("RGB").save(png_as_pdf)
        os.remove(png_path)

    plot_files = sorted(glob.glob(os.path.join(tmp_dir, "*.pdf")))
    for plot_path in plot_files:
        merger.append(plot_path)
        os.remove(plot_path)

    merged_pdf_path = os.path.join(output_dir, f"{short_filename}_light_dqm_main.pdf")
    merger.write(merged_pdf_path)
    merger.close()
    return merged_pdf_path


def main():
    start_time = time.time()
    args = parse_args()

    ptps = get_ptps(args.units)

    try:
        cs_df = pd.read_csv(args.channel_status_file, header=None)
        cs = cs_df.to_numpy()
        print(f"Channel status loaded from: {args.channel_status_file}")
    except Exception as e:
        print(f"Could not load channel status ({e}); continuing without it")
        cs = None

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.tmp_dir, exist_ok=True)

    all_files = sorted(
        f for f in os.listdir(args.input_path)
        if f.startswith(args.file_syntax) and f.endswith('.FLOW.hdf5')
    )
    if not all_files:
        print(f"No files found in {args.input_path} matching {args.file_syntax}*.FLOW.hdf5")
        sys.exit(1)
    if args.nfiles > len(all_files):
        args.nfiles = len(all_files) - args.start_run

    push_metrics = _lazy_import_grafana() if args.push_grafana else None
    proc_files = 0

    for i_file in range(args.start_run, args.start_run + args.nfiles):
        filename = f'{args.input_path}{args.file_syntax}{i_file:05d}.FLOW.hdf5'
        short_filename = os.path.basename(filename)[:-10]

        if not os.path.exists(filename):
            print(f"File not found, skipping: {filename}")
            continue
        proc_files += 1
        print(f"Processing file: {filename} with units: {args.units}")

        try:
            file = h5py.File(filename, 'r')
        except Exception as e:
            print(f"Error opening {filename}: {e}")
            continue

        meta = build_file_metadata(file, filename, args, ptps)

        if args.ncomp == -1 or args.ncomp > i_file:
            ncomps = np.arange(0, i_file)
        elif args.ncomp == 0:
            ncomps = np.array([])
        else:
            ncomps = np.arange(i_file - args.ncomp, i_file)

        metrics = run_processing(meta, args, i_file, ncomps, cs, args.tmp_dir)

        header_lines = [
            f"File index: {i_file:05d}",
            filename,
            "",
            f"Data start (CT): {meta['start_central']}",
            f"Data end   (CT): {meta['end_central']}",
            "",
        ] + [f"{k}: {v}" for k, v in metrics.items()]

        merged_pdf_path = build_report_pdf(args.tmp_dir, args.output_dir, short_filename, header_lines)
        print(f"Wrote {merged_pdf_path}")

        if args.metrics_json_out:
            with open(args.metrics_json_out, 'a') as f:
                json.dump({"file_index": i_file, "filename": filename, **metrics}, f)
                f.write('\n')

        if push_metrics is not None:
            run_tag = args.grafana_run_tag or str(i_file)
            push_metrics(
                metrics=metrics,
                tags={"run": run_tag, "stage": "light_dqm"},
                measurement="light_dqm",
            )
            print(f"Pushed {len(metrics)} metrics to Grafana/InfluxDB for run {run_tag}")

    if not proc_files:
        raise ValueError("None of the files were found")

    print(f"Time taken all files: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
