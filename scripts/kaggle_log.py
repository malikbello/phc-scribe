"""Read the Kaggle job's status and log from a cloud session, and pull out its reports.

    python scripts/kaggle_log.py                       # status + report summary
    python scripts/kaggle_log.py --save results/pilot  # also save each report JSON there

Cloud sessions cannot download Kaggle output files (kaggleusercontent.com is outside
the proxy allowlist), but the run log is readable through the API, and the job
(`kaggle/baseline/run.py`) prints every score report (=== REPORT name ===) and every
invalid-output summary (=== INVALID name ...) into it. The log is only complete after
the run ends. Needs KAGGLE_API_TOKEN; the token is never printed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KERNEL_OWNER = "bellomalik"
KERNEL_SLUG = "phc-scribe-baseline"
METRICS = ("danger_recall", "micro_f1", "false_alarm_rate", "rule_flag_recall", "schema_valid_rate")


def fetch(slug: str) -> tuple[str, str]:
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.kernels.types.kernels_api_service import (
        ApiGetKernelSessionStatusRequest,
        ApiListKernelSessionOutputRequest,
    )

    api = KaggleApi()
    api.authenticate()
    with api.build_kaggle_client() as kc:
        req = ApiGetKernelSessionStatusRequest()
        req.user_name, req.kernel_slug = KERNEL_OWNER, slug
        status = str(kc.kernels.kernels_api_client.get_kernel_session_status(req).status)
        out = ApiListKernelSessionOutputRequest()
        out.user_name, out.kernel_slug = KERNEL_OWNER, slug
        raw = kc.kernels.kernels_api_client.list_kernel_session_output(out).log or ""
    try:  # the log is a JSON list of {stream_name, time, data} events
        text = "".join(e.get("data", "") for e in json.loads(raw))
    except (json.JSONDecodeError, AttributeError):
        text = raw
    return status, text


def reports(text: str) -> dict[str, dict]:
    decoder = json.JSONDecoder()
    found = {}
    for m in re.finditer(r"=== REPORT (\S+) ===\n", text):
        found[m.group(1)], _ = decoder.raw_decode(text[m.end() :])
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default=KERNEL_SLUG)
    parser.add_argument("--save", type=Path, help="directory to write <name>.report.json files")
    args = parser.parse_args()

    status, text = fetch(args.slug)
    print(f"status: {status}")
    for line in text.splitlines():
        if (
            line.startswith(("=== INVALID", "=== BELEBELE"))
            or "secret not attached" in line
            or line.startswith("run failed")
        ):
            print(line)
    found = reports(text)
    for name, rep in found.items():
        overall = rep.get("overall", {})
        cells = [f"{k} {overall[k]['point']:.3f}" for k in METRICS if k in overall]
        print(f"{name} (n={rep.get('n_items')}): " + ", ".join(cells))
    if args.save and found:
        args.save.mkdir(parents=True, exist_ok=True)
        for name, rep in found.items():
            (args.save / f"{name}.report.json").write_text(json.dumps(rep, indent=2) + "\n")
        print(f"saved {len(found)} reports to {args.save}")
    if not found and "COMPLETE" not in status:
        print("no reports yet: the log is only complete after the run ends", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
