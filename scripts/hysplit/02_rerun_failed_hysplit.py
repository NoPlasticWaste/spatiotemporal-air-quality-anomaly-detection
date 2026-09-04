#!/usr/bin/env python3
"""
Rerun only failed HYSPLIT episodes.

This is a thin wrapper around 04_run_hysplit_batch.py logic. Supply a rerun CSV
containing only failed episodes. It uses the same portable command-line paths.

Example
-------
python 04_rerun_failed_hysplit.py \
  --hysplit-exec ~/hysplit/exec/hyts_std \
  --work-dir "/Volumes/NO NAME/hysplit-validation" \
  --requests-csv "/Volumes/NO NAME/hysplit-validation/input/hysplit_rerun_requests.csv"
"""

from pathlib import Path

# Keep this script standalone so it can be copied/run independently.
exec(
    Path(__file__).with_name("04_run_hysplit_batch.py").read_text()
    .replace(
        'if __name__ == "__main__":\n    main()\n',
        'if __name__ == "__main__":\n    main()\n'
    )
)
