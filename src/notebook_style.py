"""Shared display conventions for analysis notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display as _display


FIGURE_STYLE = {
    "figure.dpi": 110,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "semibold",
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
}

SPREADSHEET_TABLE_STYLE = [
    {"selector": "table", "props": [
        ("border-collapse", "collapse"),
        ("font-size", "12px"),
    ]},
    {"selector": "th.col_heading, th.blank", "props": [
        ("border-left", "1px solid #222"),
        ("border-right", "1px solid #222"),
        ("border-bottom", "1px solid #222"),
        ("padding", "4px 8px"),
        ("font-weight", "bold"),
        ("text-align", "center"),
    ]},
    {"selector": "th.row_heading", "props": [
        ("border-left", "1px solid #222"),
        ("border-right", "1px solid #222"),
        ("padding", "4px 8px"),
        ("font-weight", "normal"),
        ("text-align", "left"),
    ]},
    {"selector": "td", "props": [
        ("border-left", "1px solid #222"),
        ("border-right", "1px solid #222"),
        ("padding", "4px 8px"),
        ("text-align", "left"),
    ]},
]


def apply_figure_style() -> None:
    """Apply the project's shared Matplotlib defaults."""
    plt.rcParams.update(FIGURE_STYLE)


def table_style(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Return a display-only DataFrame with the shared spreadsheet-style layout."""
    display_frame = (
        frame.reset_index()
        if any(name is not None for name in frame.index.names)
        else frame.copy()
    )
    return display_frame.style.set_table_styles(SPREADSHEET_TABLE_STYLE)


def display_spreadsheet(*objects: object, **kwargs: object) -> None:
    """Display DataFrames in the shared layout; pass other objects through unchanged."""
    for object_ in objects:
        if isinstance(object_, pd.DataFrame):
            _display(table_style(object_), **kwargs)
        else:
            _display(object_, **kwargs)
