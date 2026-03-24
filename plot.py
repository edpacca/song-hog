from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import colors

spectrogram_cmap = LinearSegmentedColormap.from_list(
    "catppuccin",
    [colors.dark_mauve, colors.dark_red, colors.peach, colors.yellow]
)
from typing import Tuple
from process import detect_segments, smooth_signal

def set_axes_colors(ax):
    text_color = colors.text
    ax.spines['bottom'].set_color(text_color)
    ax.spines['left'].set_color(text_color)
    ax.spines['top'].set_color(text_color)
    ax.spines['right'].set_color(text_color)
    ax.tick_params(axis='x', colors=text_color)
    ax.tick_params(axis='y', colors=text_color)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)


def subplot_waveform(subplot, data, duration):
    subplot.plot(np.linspace(0, duration, len(data)), data, color=colors.lavender_alpha)
    # subplot.text(-0.05, 0.5, "Waveform", transform=subplot.transAxes, rotation=90, va='center', ha='center')
    subplot.set_yticks([0])
    subplot.set_xlim(0, duration)

def subplot_spectrum(subplot, data, sample_rate) -> Tuple[np.ndarray, np.ndarray]:
    spectrum, freqs, t, im = subplot.specgram(
        data,
        Fs=sample_rate,
        NFFT=1024,
        noverlap=512,
        cmap=spectrogram_cmap
    )
    # subplot.text(-0.05, 0.5, "Spectrogram", transform=subplot.transAxes, rotation=90, va='center', ha='center')
    subplot.set_ylabel("Frequency (Hz)")
    return (spectrum, t)

def subplot_spectrum_mean_intensity(subplot, intensity, color, t):
    # subplot.text(-0.05, 0.5, "Spectrogram mean", transform=subplot.transAxes, rotation=90, va='center', ha='center')
    subplot.plot(t, intensity, color=color)
    subplot.set_ylim(intensity.min(), intensity.max())

def subplot_segements(subplot, segments, alpha=0.4, color=colors.green, padding=None, padding_color=colors.maroon):
    for start, end in segments:
        subplot.axvspan(start, end, alpha=alpha, color=color)
        if padding:
            subplot.axvspan(start, start + padding, alpha=alpha, color=padding_color)
            subplot.axvspan(end - padding, end, alpha=alpha, color=padding_color)

def plot_data(
        data,
        sample_rate,
        file_name,
        outdir,
        window=400,
        threshold=35,
        min_duration=40,
        min_gap=20,
        padding=5,
        export=True,
        show=False):
    duration = len(data)/sample_rate

    fig, (ax1, ax2, ax3) = plt.subplots(
        nrows=3, ncols=1,
        sharex='all',
        figsize=(12, 6),
        facecolor=colors.mantle)

    ax1.set_facecolor(colors.base)
    ax2.set_facecolor(colors.base)
    ax3.set_facecolor(colors.base)
    set_axes_colors(ax1)
    set_axes_colors(ax2)
    set_axes_colors(ax3)

    # Waveform
    subplot_waveform(ax1, data, duration)

    # Spectrum
    spectrum, t = subplot_spectrum(ax2, data, sample_rate)
    # fig.colorbar(ax=ax2, label="Intensity (dB)")

    # Mean plot
    avg_intensity = spectrum.mean(axis=0)
    avg_intensity[avg_intensity == 0] = 1e-10     # replace 0 values to avoid -inf after log transform

    avg_intensity_db = 10 * np.log10(avg_intensity)
    avg_intensity_db[avg_intensity_db < 0] = 0    # clamp at 0

    smoothed_intensity = smooth_signal(avg_intensity_db, window)

    segments = detect_segments(smoothed_intensity, t, threshold, min_duration, min_gap, padding)
    subplot_segements(ax3, segments, 0.4, colors.lavender, padding=padding, padding_color=colors.red)
    subplot_segements(ax1, segments, 0.3, colors.green, padding=padding, padding_color=colors.pink)
    # subplot_spectrum_mean_intensity(ax3, avg_intensity_db, colors.surface_2, t)
    subplot_spectrum_mean_intensity(ax3, smoothed_intensity, colors.peach, t)
    # plot threshold
    ax3.plot([0, t[-1]], [threshold, threshold], color=colors.sapphire)

    # format labels
    ax3.set_xlabel("Time (min)")
    ax3.xaxis.set_major_locator(ticker.MultipleLocator(300))
    ax3.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x / 60)}"))
    ax3.xaxis.set_minor_locator(ticker.MultipleLocator(60))
    ax3.xaxis.set_minor_formatter(ticker.NullFormatter())

    # format margins
    ax1.margins(x=0)
    ax2.margins(x=0)
    ax3.margins(x=0)
    fig.tight_layout()

    plt.subplots_adjust(hspace=0)
    fig.subplots_adjust(hspace=0)
    params = f"window={window},  threshold={threshold}dB,  min_duration={min_duration}s,  min_gap={min_gap}s,  padding={padding}s"
    plt.text(0.5, 0.1, params, color=colors.text)

    if export:
        png_name = f"{file_name}__segment_plot__w_{window}__th_{threshold}__md_{min_duration}__mg_{min_gap}__p_{padding}.png"
        fig.savefig(Path(outdir) / png_name, dpi=150, bbox_inches="tight")
        plt.close('all')
    if show:
        plt.show()
    return segments
