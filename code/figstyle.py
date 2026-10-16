"""Shared, colour-blind-safe Matplotlib style for all four papers' figures.

The figures follow the Open Research Europe figure guidelines for line art. Every figure is drawn at
the width at which it will be displayed, at most 150 mm (two columns), so that the text, set at
8 pt or more, keeps that size on the page, on a white background in RGB. Each figure is saved as
EPS and PDF, which are vector formats and the preferred format for graphs, and as a 600 dpi RGB PNG
with its resolution recorded in the file, which is embedded in the Word manuscript and from which an
uncompressed 600 dpi TIFF is made for submission (see make_submission_figures.py).
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image

# Okabe and Ito colour-blind-safe palette
OKABE = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "red": "#D55E00",
         "purple": "#CC79A7", "sky": "#56B4E9", "yellow": "#F0E442", "black": "#000000",
         "grey": "#999999"}
SEQ = [OKABE["blue"], OKABE["orange"], OKABE["green"], OKABE["red"], OKABE["purple"], OKABE["sky"]]

WIDTH_IN = 150 / 25.4      # two column display width of Open Research Europe, 150 mm
DPI = 600                  # line art raster resolution required when no vector file is used


def apply():
    mpl.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": DPI, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
        "figure.facecolor": "white", "savefig.facecolor": "white", "axes.facecolor": "white",
        "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
        "legend.frameon": False, "legend.fontsize": 8,
        "lines.linewidth": 1.4, "lines.markersize": 4,
        "font.family": "DejaVu Sans", "ps.fonttype": 42, "pdf.fonttype": 42,
    })


def save(fig, path):
    fig.savefig(path + ".pdf")
    fig.savefig(path + ".eps")
    fig.savefig(path + ".png", dpi=DPI)
    im = Image.open(path + ".png").convert("RGB")
    im.save(path + ".png", dpi=(DPI, DPI), optimize=True)
    plt.close(fig)
