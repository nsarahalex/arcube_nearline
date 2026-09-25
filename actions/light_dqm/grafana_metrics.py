#!/usr/bin/env python3
"""
grafana_metrics.py

Pushes per-file DQM metrics to the InfluxDB instance that backs the light
DQM Grafana dashboards. Called from light_dqm_skeleton.py's main() when
--push_grafana is set.

Connection details (URL, PORT, NAME, PINGIP, and optional USERNAME/PASSWORD)
live in config/grafana_config.yaml, not in this file - see
config/templates/grafana_config.template.yaml for the expected format and
admin/install.sh for how that file gets created from the template.

Nothing in here ever raises: a failed push should never take down a DQM run
that otherwise succeeded, so every failure mode prints a message and returns
False instead.
"""

import os
import subprocess
import time

import yaml
from influxdb import InfluxDBClient

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG_PATH = os.path.join(_THIS_DIR, "..", "..", "config", "grafana_config.yaml")


def _load_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)


def _host_reachable(ip, timeout_s=2):
    """
    Plain ICMP ping - PINGIP is a general "are we on the DAQ network at all"
    check, separate from (and cheaper than) actually trying to reach the
    InfluxDB port. Never raises; treats any error as unreachable.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_s), ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except Exception:
        return False


def push_metrics(metrics, tags, measurement, config_path=_DEFAULT_CONFIG_PATH):
    """
    Push a dict of scalar metrics to InfluxDB as a single point.

    Args:
        metrics: dict of {field_name: numeric_value}, e.g. the `metrics`
            dict built by run_processing() in light_dqm_skeleton.py.
        tags: dict of {tag_name: value} used to index/filter the point in
            Grafana, e.g. {"run": "123", "stage": "light_dqm"}.
        measurement: InfluxDB measurement name (roughly: table name).
        config_path: override for the config file location (mainly for
            testing without touching the real config/grafana_config.yaml).

    Returns:
        True if the write succeeded, False otherwise.
    """
    try:
        cfg = _load_config(config_path)
    except Exception as e:
        print(f"[grafana_metrics] Could not load config from {config_path}: {e}")
        return False

    ping_ip = cfg.get("PINGIP")
    if ping_ip and not _host_reachable(ping_ip):
        print(f"[grafana_metrics] {ping_ip} not reachable; skipping Grafana push")
        return False

    host = cfg["URL"].replace("http://", "").replace("https://", "")

    try:
        client = InfluxDBClient(
            host=host,
            port=cfg["PORT"],
            username=cfg.get("USERNAME"),
            password=cfg.get("PASSWORD"),
            database=cfg["NAME"],
        )
        existing_dbs = [db["name"] for db in client.get_list_database()]
        if cfg["NAME"] not in existing_dbs:
            client.create_database(cfg["NAME"])
    except Exception as e:
        print(f"[grafana_metrics] Could not connect to InfluxDB at {host}:{cfg['PORT']}: {e}")
        return False

    point = {
        "measurement": measurement,
        "tags": tags,
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fields": {k: float(v) for k, v in metrics.items()},
    }

    try:
        client.write_points([point])
    except Exception as e:
        print(f"[grafana_metrics] Failed to write metrics to InfluxDB: {e}")
        return False

    return True
