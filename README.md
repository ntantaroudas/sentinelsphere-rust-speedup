# Separating algorithmic change from language change in a Rust rewrite of a real time threat scorer

Code and data for the Open Research Europe article "Separating algorithmic change from language change in a Rust rewrite of a real time threat scorer" by Nikolaos D. Tantaroudas, Ilias Karachalios and Andrew J. McCracken, a follow on study of the SentinelSphere platform carried out under the Horizon Europe project ResilMesh, Grant Agreement No. 101119681.

Preprint of the short version, https://doi.org/10.48550/arXiv.2610.07931.

## Contents and how to reproduce

Code and measurements for "Where does a Rust speedup come from? Language and algorithm effects in a sliding window threat scorer".

`code/python` holds the three Python scorers, `code/rust` the Rust crate with the two Rust scorers, `code/run_benchmarks.py` the harness and `code/analyse.py` the analysis and plotting script. `results/raw_timings.jsonl` holds every timed repetition, `results/summary.csv` the medians, `results/decomposition.csv` the language and algorithm factors and `results/paperA_numbers.json` the numbers quoted in the text.

To reproduce, build the crate in `code/rust` with `cargo build --release`, then run `python3 code/run_benchmarks.py`, which takes about forty minutes on two cores, and `python3 code/analyse.py`.

The analysis scripts import `figstyle.py` from the folder `code`, which sets the figure style used in the article, drawn at a display width of at most 150 mm and saved as EPS, PDF and 600 dpi PNG.

## Licence

The code is released under the MIT License, see `LICENSE`. The aggregated results and figures are released under the Creative Commons Zero 1.0 dedication, see `DATA_LICENSE.md`.

## Citation

Please cite the article, and this repository through its Zenodo DOI once a release has been archived, see `CITATION.cff`.
