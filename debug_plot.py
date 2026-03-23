from matplotlib import widgets
import matplotlib.pyplot as plt
import numpy as np

def plot_data(data, sample_rate):
    fig = plt.figure(figsize=(28, 12))
    duration = len(data)/sample_rate
    plt.subplot(3, 1, 1)
    plt.plot(np.linspace(0, duration, len(data)), data)
    plt.title("Waveform")
    plt.xlabel("Time (s)")
    plt.xlim(0, duration)
    plt.margins(x=0)

    ax1 = plt.subplot(3, 1, 2)
    spectrum, freqs, t, im = plt.specgram(data, Fs=sample_rate, NFFT=1024, noverlap=512, cmap='inferno')
    plt.title("Spectrogram")
    plt.xlabel("Time (s)")
    plt.xlim(0, duration)

    avg_intensity = spectrum.mean(axis=0)
    avg_intensity_db = 10 * np.log10(avg_intensity)

    ax2 = plt.subplot(3, 1, 3)
    plt.title("Spectrogram mean")
    plt.xlabel("Time (s)")
    plt.xlim(0, duration)
    ax2.plot(t, avg_intensity_db)

    init_window = 800
    init_threshold = 35        # dB value below which we consider it "not music" — tune to your data
    init_min_duration = 50     # minimum continuous seconds to count as a music segment

    smoothed = np.convolve(avg_intensity_db, np.ones(init_window) / init_window, mode="same")
    smoothed_line, = ax2.plot(t, smoothed, color="orange")
    spans= []
    # plt.ylabel("Frequency (Hz)")
    # plt.ylim(0, 4000)
    # plt.colorbar(label="Intensity (dB)")

    plt.subplots_adjust(bottom=0.25)

    # # Boolean mask where signal is above threshold
    # is_music = smoothed > threshold

    # # Convert time bins to seconds using t array
    # dt = t[1] - t[0]  # seconds per bin
    # min_bins = int(min_duration / dt)

    # # Find contiguous runs above threshold
    # segments = []
    # in_segment = False
    # start = 0

    # for i, val in enumerate(is_music):
    #     if val and not in_segment:
    #         start = i
    #         in_segment = True
    #     elif not val and in_segment:
    #         in_segment = False
    #         if (i - start) >= min_bins:
    #             segments.append((t[start], t[i]))  # (start_sec, end_sec)

    # # catch segment running to end
    # if in_segment and (len(is_music) - start) >= min_bins:
    #     segments.append((t[start], t[-1]))

    # print(segments)
    # for start, end in segments:
    #     plt.axvspan(start, end, alpha=0.3, color='green')

    def update(_):
        threshold = threshold_slider.val
        min_duration = duration_slider.val
        window = int(window_slider.val)

        # recompute smoothed
        new_smoothed = np.convolve(avg_intensity_db, np.ones(window)/window, mode='same')
        smoothed_line.set_ydata(new_smoothed)

        # remove old spans
        for span in spans:
            span.remove()
        spans.clear()

        # recompute segments
        is_music = new_smoothed > threshold
        dt = t[1] - t[0]
        min_bins = int(min_duration / dt)
        in_segment = False
        start = 0
        for i, val in enumerate(is_music):
            if val and not in_segment:
                start = i
                in_segment = True
            elif not val and in_segment:
                in_segment = False
                if (i - start) >= min_bins:
                    spans.append(ax2.axvspan(t[start], t[i], alpha=0.3, color='green'))
        if in_segment and (len(is_music) - start) >= min_bins:
            spans.append(ax2.axvspan(t[start], t[-1], alpha=0.3, color='green'))

        fig.canvas.draw_idle()

    # --- sliders ---
    ax_thresh   = plt.axes([0.15, 0.15, 0.7, 0.03])
    ax_duration = plt.axes([0.15, 0.10, 0.7, 0.03])
    ax_window   = plt.axes([0.15, 0.05, 0.7, 0.03])

    threshold_slider = widgets.Slider(ax_thresh,   'Threshold',    0,   60,  valinit=init_threshold)
    duration_slider  = widgets.Slider(ax_duration, 'Min Duration', 1,  120,  valinit=init_min_duration)
    window_slider    = widgets.Slider(ax_window,   'Smooth Window', 10, 2000, valinit=init_window)

    threshold_slider.on_changed(update)
    duration_slider.on_changed(update)
    window_slider.on_changed(update)

    update(None)  # draw initial state
    plt.show()


    plt.tight_layout()
    plt.show()
