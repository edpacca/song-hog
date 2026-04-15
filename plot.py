import logging
import re
from pathlib import Path
from typing import Tuple
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import colors

spectrogram_cmap = LinearSegmentedColormap.from_list(
    "catppuccin", [colors.dark_mauve, colors.dark_red, colors.peach, colors.yellow]
)
from process import AudioAnalysis

logger = logging.getLogger(__name__)


def set_axes_colors(ax):
    text_color = colors.text
    ax.spines["bottom"].set_color(text_color)
    ax.spines["left"].set_color(text_color)
    ax.spines["top"].set_color(text_color)
    ax.spines["right"].set_color(text_color)
    ax.tick_params(axis="x", colors=text_color)
    ax.tick_params(axis="x", which="minor", colors=text_color)
    ax.tick_params(axis="y", colors=text_color)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)


def subplot_waveform(subplot, data, duration):
    subplot.plot(np.linspace(0, duration, len(data)), data, color=colors.lavender_alpha)
    subplot.set_yticks([0])
    subplot.set_xlim(0, duration)
    subplot.set_ylabel("Amplitude")


def subplot_spectrum(subplot, analysis: AudioAnalysis):
    spectrum_db = 10 * np.log10(np.maximum(analysis.spectrum, 1e-10))
    mesh = subplot.pcolormesh(
        analysis.t, analysis.freqs, spectrum_db, cmap=spectrogram_cmap, shading="auto"
    )
    subplot.set_ylabel("Freq. (Hz)")
    subplot.yaxis.set_major_formatter(
        ticker.FuncFormatter(
            lambda x, _: f"{int(x // 1000)}k" if x >= 1000 else str(int(x))
        )
    )
    return mesh


def subplot_spectrum_mean_intensity(subplot, intensity, color, t):
    subplot.plot(t, intensity, color=color)
    subplot.set_ylim(intensity.min(), intensity.max())
    subplot.set_ylabel("Mean int. (dB)")


def subplot_colorbar(fig, mesh, ax_pos):
    cbar_ax = fig.add_axes([0.91, ax_pos.y0, 0.02, ax_pos.height])
    cbar = fig.colorbar(mesh, cax=cbar_ax)

    vmin, vmax = mesh.norm.vmin, mesh.norm.vmax
    cbar.set_ticks([vmin, 0, vmax])
    cbar.set_ticklabels([f"{vmin:.0f}", "0", f"{vmax:.0f}"])
    plt.setp(cbar.ax.get_yticklabels(), rotation=90, va="center", color=colors.text)
    cbar.ax.yaxis.set_tick_params(colors=colors.text)
    cbar.outline.set_edgecolor(colors.text)

    cbar.ax.set_xlabel("dB", color=colors.text, rotation=0, labelpad=6)
    cbar.ax.xaxis.label.set_color(colors.text)


def subplot_segements(
    subplot,
    segments,
    alpha=0.4,
    color=colors.green,
    padding=None,
    padding_color=colors.maroon,
):
    for start, end in segments:
        subplot.axvspan(start, end, alpha=alpha, color=color)
        if padding:
            subplot.axvspan(start, start + padding, alpha=alpha, color=padding_color)
            subplot.axvspan(end - padding, end, alpha=alpha, color=padding_color)


def plot_data(
    analysis: AudioAnalysis,
    data,
    file_name,
    outdir,
    export=True,
    show=False,
):
    logger.info(f"Plotting: {file_name}")
    duration = analysis.t[-1]

    fig, (ax1, ax2, ax3) = plt.subplots(
        nrows=3, ncols=1, sharex="all", figsize=(12, 6), facecolor=colors.mantle
    )

    ax1.set_facecolor(colors.base)
    ax2.set_facecolor(colors.base)
    ax3.set_facecolor(colors.base)
    set_axes_colors(ax1)
    set_axes_colors(ax2)
    set_axes_colors(ax3)

    # Waveform
    subplot_waveform(ax1, data, duration)

    # Spectrum
    mesh = subplot_spectrum(ax2, analysis)

    # Mean intensity plot
    subplot_segements(
        ax3,
        analysis.segments,
        0.4,
        colors.lavender,
        padding=analysis.params.padding,
        padding_color=colors.red,
    )
    subplot_segements(
        ax1,
        analysis.segments,
        0.3,
        colors.green,
        padding=analysis.params.padding,
        padding_color=colors.pink,
    )
    subplot_spectrum_mean_intensity(ax3, analysis.smoothed, colors.peach, analysis.t)
    # plot threshold
    ax3.plot([0, analysis.t[-1]], [analysis.params.threshold, analysis.params.threshold], color=colors.sapphire)

    # format labels
    _format_x_axis(ax3, False)

    # format margins
    ax1.margins(x=0)
    ax2.margins(x=0)
    ax3.margins(x=0)

    # Reserve right space for colorbar and top space for params text
    fig.subplots_adjust(hspace=0, right=0.90, top=0.93)

    # Colorbar aligned with spectrogram (ax2) only
    subplot_colorbar(fig, mesh, ax2.get_position())

    # Parameters text at top
    fig.text(
        0.5, 0.97, f"sample rate: {analysis.sample_rate // 1000}kbs {str(analysis.params)}", color=colors.text, ha="center", va="top"
    )

    if export:
        save_figure(fig, outdir, f"{file_name}__segment_plot__{repr(analysis.params)}")
    if show:
        plt.show()
    return fig


def save_figure(fig, outdir, name):
    png_name = f"{name}.png"
    fig.savefig(Path(outdir) / png_name, dpi=150, bbox_inches="tight")
    logger.info(f"Plot saved: {png_name}")
    plt.close(fig)


_SEGMENT_COLORS = [
    colors.lavender, colors.green, colors.teal, colors.sky,
    colors.blue, colors.mauve, colors.pink, colors.peach,
]


def _format_x_axis(ax, minutes = True):
    if minutes:
        ax.set_xlabel("Time (min.)")
        ax.xaxis.set_major_locator(ticker.MultipleLocator(300))
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x / 60)}"))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(60))
        ax.xaxis.set_minor_formatter(ticker.NullFormatter())
    else:
        ax.set_xlabel("Time (s)")


def _param_label(analysis: AudioAnalysis, factor: str) -> str:
    match = re.search(rf"{re.escape(factor)}=([^\s]+)", str(analysis.params))
    return f"{factor}={match.group(1)}" if match else repr(analysis.params)


def experimental_plots_compare_segments(
    control_analysis: AudioAnalysis,
    compare_analyses: list[AudioAnalysis],
    compare_factor: str,
    control_analysis_y_range: Tuple[ int, int ] = None
):
    n = len(compare_analyses)
    height_ratios = [3] + [1] * n
    fig, axes = plt.subplots(
        nrows=1 + n,
        ncols=1,
        sharex="all",
        figsize=(14, 2 + n * 0.8),
        facecolor=colors.mantle,
        gridspec_kw={"height_ratios": height_ratios},
    )

    # Smoothed reference curve (shared across all analyses)
    ax_smooth = axes[0]
    ax_smooth.set_facecolor(colors.base)
    set_axes_colors(ax_smooth)
    ax_smooth.plot(control_analysis.t, control_analysis.smoothed, color=colors.peach, linewidth=1)
    ax_smooth.set_ylabel("Mean int. (dB)")
    ax_smooth.margins(x=0)

    if control_analysis_y_range:
        ax_smooth.set_ylim(control_analysis_y_range[0], control_analysis_y_range[1])

    # If comparing threshold, overlay each threshold line on the smoothed plot
    if compare_factor == "threshold":
        for i, analysis in enumerate(compare_analyses):
            m = re.search(r"threshold=([0-9.]+)", str(analysis.params))
            if m:
                ax_smooth.axhline(
                    float(m.group(1)),
                    color=_SEGMENT_COLORS[i % len(_SEGMENT_COLORS)],
                    linewidth=0.8, linestyle="--", alpha=0.85,
                )

    # One condensed row per analysis showing only detected segments
    for i, analysis in enumerate(compare_analyses):
        ax = axes[i + 1]
        ax.set_facecolor(colors.base)
        set_axes_colors(ax)
        c = _SEGMENT_COLORS[i % len(_SEGMENT_COLORS)]
        for start, end in analysis.segments:
            ax.axvspan(start, end, alpha=0.65, color=c)
        ax.set_yticks([])
        ax.set_ylabel(
            _param_label(analysis, compare_factor),
            fontsize=8, color=colors.text, rotation=0, labelpad=55, va="center",
        )
        ax.margins(x=0)

    _format_x_axis(axes[-1])
    fig.suptitle(f"Comparing {compare_factor}", color=colors.text, y=0.98)
    fig.text(
        0.5, 0.94,
        f"sample rate: {control_analysis.sample_rate // 1000}kbs  {str(analysis.params)}",
        color=colors.text, ha="center", va="top", fontsize=8,
    )
    fig.subplots_adjust(hspace=0.05, top=0.90, right=0.97)
    return fig


def experimental_plots_compare_smoothed_and_segments(
    compare_analyses: list[AudioAnalysis],
    compare_factor: str,
):
    n = len(compare_analyses)
    fig, axes = plt.subplots(
        nrows=n,
        ncols=1,
        sharex="all",
        figsize=(14, 2.2 * n),
        facecolor=colors.mantle,
    )
    if n == 1:
        axes = [axes]

    for i, analysis in enumerate(compare_analyses):
        ax = axes[i]
        ax.set_facecolor(colors.base)
        set_axes_colors(ax)
        c = _SEGMENT_COLORS[i % len(_SEGMENT_COLORS)]
        subplot_segements(ax, analysis.segments, alpha=0.25, color=c)
        ax.plot(analysis.t, analysis.smoothed, color=c, linewidth=1)
        ax.set_ylabel(
            _param_label(analysis, compare_factor),
            fontsize=8, color=colors.text, rotation=0, labelpad=25, va="center",
        )
        ax.margins(x=0)

    _format_x_axis(axes[-1])
    fig.suptitle(f"Comparing {compare_factor}", color=colors.text, y=0.98)
    fig.text(
        0.5, 0.94,
        f"sample rate: {compare_analyses[0].sample_rate // 1000}kbs  {str(compare_analyses[0].params)}",
        color=colors.text, ha="center", va="top", fontsize=8,
    )
    fig.subplots_adjust(hspace=0.1, top=0.90, right=0.97)
    return fig
