"""
06_run_all.py
=============
Master script to run the entire analysis pipeline in sequence.

Usage:
    python code/06_run_all.py
"""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(BASE_DIR, "code")

scripts = [
    ("01_download_datasets.py", "Download external datasets"),
    ("02_build_analytic_dataset.py", "Build county-level analytic dataset"),
    ("03_descriptive_analysis.py", "Generate Table 1 (descriptive statistics)"),
    ("04_choropleth_map.py", "Generate Figure 1 (choropleth map)"),
    ("05_regression_analysis.py", "Run regression models"),
]


def main():
    print("=" * 60)
    print("RUNNING FULL ANALYSIS PIPELINE")
    print("=" * 60)
    
    for script, description in scripts:
        print(f"\n{'━' * 60}")
        print(f"▶ {description}")
        print(f"  Script: {script}")
        print(f"{'━' * 60}")
        
        result = subprocess.run(
            [sys.executable, os.path.join(CODE_DIR, script)],
            capture_output=False
        )
        
        if result.returncode != 0:
            print(f"\n  ✗ FAILED: {script} (exit code {result.returncode})")
            print("  Pipeline halted.")
            sys.exit(1)
        
        print(f"  ✓ Completed: {script}")
    
    print(f"\n{'━' * 60}")
    print("✓ ALL STEPS COMPLETED SUCCESSFULLY")
    print(f"{'━' * 60}")
    print(f"\nOutputs:")
    print(f"  Dataset:    data/processed/county_analytic_dataset.csv")
    print(f"  Geo data:   data/processed/county_analytic_geo.gpkg")
    print(f"  Table 1:    output/tables/table1_descriptive.csv")
    print(f"  Figure 1:   output/figures/figure1_choropleth.pdf")
    print(f"  Regression: output/models/regression_results.txt")


if __name__ == "__main__":
    main()
