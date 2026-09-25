#!/usr/bin/env bash
# This script is a wrapper for the light DQM (Data Quality Monitoring) process. It sets up the environment, defines input and output paths, checks file sizes, and runs the light DQM Python script with appropriate arguments. It also handles logging and creates a symlink to the latest output for easy access.
stage=light_dqm

# Load the initialization script to set up environment variables and functions
source $(dirname $BASH_SOURCE)/../lib/init.inc.sh

# Define the base directory for input files
inbase=$nearline_root/flowed_light
# For example, inpath = .../flowed_light/warm_commission/mpd_run_dbg_rctl_00123.FLOW.hdf5
inpath=$1; shift
indir=$(dirname "$inpath")
reldir=$(echo "$indir" | sed "s|^$inbase/||")

# Define the base directories for output files
# Strip extension and trailing run/subrun numbers, same as the original script
file_syntax=$(basename "$inpath" .FLOW.hdf5 | sed 's/[0-9]\+$//')
start_run=$(basename "$inpath" .FLOW.hdf5 | sed -n 's/.*[^0-9]\([0-9]\+\)$/\1/p')



echo "Starting run with p$start_run"
# Define the base directories for plots, logs, and metrics
# Define a function to generate output paths based on the input path, output base, tag, and extension
get_outpath() {
    outbase=$1
    tag=$2
    ext=$3
    outname=$(basename "$inpath" .FLOW.hdf5)_light_dqm_${tag}.$ext
    mkdir -p "$outbase/$reldir"
    realpath "$outbase/$reldir/$outname"
}
# Define the path to the channel status CSV file
channel_status=$(dirname "${BASH_SOURCE[0]}")/light_dqm/channel_status_warmRun2.csv
# Define output paths for plots, logs, and metrics
plotpath1=$(get_outpath "$plot_outbase" main pdf)
logpath=$(get_outpath "$log_outbase" log)
metricspath=$(get_outpath "$json_outbase" metrics json)

cd "$(dirname "${BASH_SOURCE[0]}")/light_dqm"

# Check if the input file is larger than 50 GB, and if so, exit with an error
if [[ "$(stat -c %s "$inpath")" -gt 50000000000 ]]; then
    echo "File is larger than 50 GB; bailing"
    exit 1
fi

# Grafana input flag is set by the ARCUBE_NEARLINE_PUSH_GRAFANA environment variable, which is set in the nearline service config
push_grafana_flag=""
if [[ "${ARCUBE_NEARLINE_PUSH_GRAFANA:-0}" == "1" ]]; then
    push_grafana_flag="--push_grafana --grafana_run_tag $start_run"
fi

# Run the light DQM script
python3 light_dqm_skeleton.py --input_path "$inbase/$reldir/" \
                     --output_dir "$(dirname "$plotpath1")" \
                     --tmp_dir "$plot_outbase/tmp" \
                     --file_syntax "$file_syntax" \
                     --channel_status_file "$channel_status" \
                     --start_run $start_run \
                     --metrics_json_out "$metricspath" \
                     $push_grafana_flag \
                     2>&1 | tee "$logpath"

# Create a symlink to the latest output for easy access
latest_outbase="$plot_outbase/latest"
latest_path1="$latest_outbase/latest_main.pdf"

# Create the latest output directory and symlink to the latest plot
mkdir -p "$latest_outbase"
ln -sf $plotpath1 $latest_path1