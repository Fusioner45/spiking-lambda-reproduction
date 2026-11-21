"""Run the repository's complete validation suite.

This is the canonical local counterpart of ``.github/workflows/validate.yml``.
The individual banks use assertions as their test mechanism, so this runner
refuses Python's optimized mode, where assertions are disabled.
"""

from __future__ import print_function

import argparse
import subprocess
import sys


BANKS = (
    "run_demo", "run_bridge", "run_det", "run_freevars", "run_intg",
    "run_persist", "run_copy", "run_bind", "run_ring", "run_loop",
    "run_snn_core", "run_robustness", "run_noise", "run_envelope",
    "run_scale", "run_cube", "run_rescan", "run_multiplex",
    "run_ablation", "run_stress", "run_balance", "run_envelope_profile",
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run all validation banks in the CI order.")
    parser.add_argument("--list", action="store_true",
                        help="print the bank names and exit")
    args = parser.parse_args(argv)

    if not __debug__:
        parser.error("run without -O: validation assertions would be disabled")

    if args.list:
        print("\n".join(BANKS))
        return 0

    for bank in BANKS:
        print("=== %s ===" % bank, flush=True)
        subprocess.check_call([sys.executable, bank + ".py"])

    print("All %d validation banks passed." % len(BANKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
