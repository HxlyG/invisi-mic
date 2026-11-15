"""Visualize source localization estimates in a simulated 3D room.


Run from the backend directory:
    python3 tests/visulization/visualize_localization.py
    python3 tests/visulization/visualize_localization.py --rt60 0.3 --snr-db 20 
    python3 tests/visulization/visualize_localization.py --seed 7
    python3 tests/visulization/visualize_localization.py --chirp
    python3 tests/visulization/visualize_localization.py --rt60 0.3 --snr-db 20 --seed 7
    python3 tests/visulization/visualize_localization.py --source-gap-s 1.0
    python3 tests/visulization/visualize_localization.py --source-start-s 0 --source-start-s 1.5 --source-start-s 3.0
    python3 tests/visulization/visualize_localization.py --rt60 0.3 --snr-db 20 --plot-onset-window
    python3 tests/visulization/visualize_localization.py --mic 0.5,0.5,0.5 --mic 4.5,0.5,0.5 --mic 0.5,3.5,0.5 --mic 2.5,2,2.8 --source 2,1.5,1.6
    python3 tests/visulization/visualize_localization.py --rt60 0.3 --snr-db 20 --full-recording
    python3 tests/visulization/visualize_localization.py --save-only


Each target is simulated and localized separately, with its audio emission
staggered in recording time. This isolates overlapping speakers so the plot
validates the localization pipeline, not multi-speaker separation from one
mixed recording. In the interactive window, choose a trial, scrub the shared
time cursor, select a microphone, and play/stop that microphone's recording.
"""


from __future__ import annotations


import argparse
from pathlib import Path
import random
import sys
import time


import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from matplotlib.figure import Figure
from matplotlib.widgets import Button, Slider
from matplotlib.lines import Line2D
from scipy.signal import resample_poly
from typing import Any, cast


# Allow both `python -m tests.visualize_localization` and direct execution
# from the backend directory.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))


from src.Algorithm.calibration import localize_chirp_source
from src.Algorithm.solver import solve_position
from src.Algorithm.tdoa import estimate_tdoa_frame_consensus
from src.Algorithm.onset import OnsetDetection, shared_onset_window
from src.Simulation.signals import AudioSource, make_chirp, simulate_room




ROOM_DIMENSIONS = (5.0, 4.0, 3.0)
SAMPLE_RATE = 16_000
MICROPHONE_POSITIONS = np.array(
    (
        (0.5, 0.5, 0.5),
        (4.5, 0.5, 0.5),
        (0.5, 3.5, 0.5),
        (2.5, 2.0, 2.8),
    ),
    dtype=np.float64,
)
SOURCE_POSITIONS = np.array(
    (
        (1.0, 1.0, 1.5),
        (2.5, 1.0, 1.5),
        (4.0, 3.0, 1.5),
        (1.2, 3.0, 2.2),
        (3.8, 0.8, 2.4),
    ),
    dtype=np.float64,
)
DEFAULT_SPEECH_DATASET = (
    BACKEND_ROOT
    / "data"
    / "speech"
    / "LibriSpeech"
    / "dev-clean"
)




def run_visual_test(
    *,
    room_dimensions: tuple[float, float, float] = ROOM_DIMENSIONS,
    microphone_positions: np.ndarray = MICROPHONE_POSITIONS,
    source_positions: np.ndarray = SOURCE_POSITIONS,
    reverberation_time_s: float | None = None,
    snr_db: float | None = None,
    time_window_s: tuple[float, float] | None = None,
    auto_onset_window: bool = True,
    pre_roll_s: float = 0.005,
    event_duration_s: float = 0.5,
    onset_noise_window_s: tuple[float, float] | None = None,
    source_start_times_s: np.ndarray | None = None,
    source_gap_s: float = 0.75,
    chirp_min_peak_ratio: float = 0.05,
    speech_dataset_dir: Path | None = DEFAULT_SPEECH_DATASET,
    use_chirp: bool = False,
    random_seed: int | None = None,
    plot_onset_window: bool = False,
    show_plot: bool = True,
    output_path: Path | None = None,
) -> list[tuple[np.ndarray, np.ndarray, float]]:
    """Simulate targets, estimate their positions, and plot the results.


    Returns a list of (actual position, estimated position, position error)
    tuples so the run can also be inspected programmatically.
    """
    room_size = np.asarray(room_dimensions, dtype=np.float64)
    room_dimensions_tuple = tuple(float(value) for value in room_size)
    microphones = np.asarray(microphone_positions, dtype=np.float64)
    sources = np.asarray(source_positions, dtype=np.float64)
    if room_size.shape != (3,) or not np.all(np.isfinite(room_size)) or np.any(room_size <= 0):
        raise ValueError("room_dimensions must be three positive finite lengths")
    if microphones.ndim != 2 or microphones.shape[1] != 3 or microphones.shape[0] == 0:
        raise ValueError("microphone_positions must contain one or more 3D coordinates")
    if sources.ndim != 2 or sources.shape[1] != 3 or sources.shape[0] == 0:
        raise ValueError("source_positions must contain one or more 3D coordinates")
    if not np.isfinite(source_gap_s) or source_gap_s < 0:
        raise ValueError("source_gap_s must be non-negative and finite")
    if source_start_times_s is None:
        start_times = np.arange(sources.shape[0], dtype=np.float64) * source_gap_s
    else:
        start_times = np.asarray(source_start_times_s, dtype=np.float64)
        if start_times.shape != (sources.shape[0],):
            raise ValueError("provide exactly one source start time per source position")
        if not np.all(np.isfinite(start_times)) or np.any(start_times < 0):
            raise ValueError("source start times must be non-negative and finite")
    if not np.isfinite(chirp_min_peak_ratio) or not 0 < chirp_min_peak_ratio <= 1:
        raise ValueError("chirp_min_peak_ratio must be in the interval (0, 1]")


    if use_chirp:
        speech_files: list[Path] = []
        rng = random.Random(random_seed)
    else:
        speech_files = _find_speech_files(speech_dataset_dir) if speech_dataset_dir is not None else []
        if not speech_files:
            print(f"No speech clips found under {speech_dataset_dir}; using generated chirps.")
            use_chirp = True
        rng = random.Random(random_seed)
    chirp = make_chirp(
        SAMPLE_RATE,
        duration_s=0.02,
        start_hz=1_500,
        end_hz=7_000,
    ) if use_chirp else None
    if use_chirp:
        # Leave quiet samples before emission for matched-filter noise calibration.
        start_times = start_times + 0.1
    max_phone_spacing = float(
        np.max(
            np.linalg.norm(
                microphones[:, None, :] - microphones[None, :, :],
                axis=2,
            )
        )
    )
    max_delay_s = max_phone_spacing / 343.0


    results: list[tuple[np.ndarray, np.ndarray, float]] = []
    microphone_recordings: list[np.ndarray] = []
    used_audio_files: list[str] = []
    used_start_times: list[float] = []
    window_diagnostics: list[
        tuple[tuple[float, float] | None, tuple[OnsetDetection, ...]]
    ] = []
    for index, actual_position in enumerate(sources):
        if use_chirp:
            assert chirp is not None
            audio_signal = chirp
            audio_label = "generated chirp"
        else:
            assert speech_dataset_dir is not None
            audio_path = rng.choice(speech_files)
            audio_signal = _load_audio_mono(audio_path, SAMPLE_RATE)
            audio_label = str(audio_path.relative_to(speech_dataset_dir))
        used_audio_files.append(audio_label)
        used_start_times.append(float(start_times[index]))
        simulation = simulate_room(
            room_dimensions=room_dimensions_tuple,
            microphone_positions=microphones,
            sources=(
                AudioSource(
                    tuple(float(value) for value in actual_position),
                    audio_signal,
                    delay_s=float(start_times[index]),
                ),
            ),
            sample_rate=SAMPLE_RATE,
            reverberation_time_s=reverberation_time_s,
            snr_db=snr_db,
            noise_seed=(random_seed + index if random_seed is not None else 100 + index),
        )
        microphone_recordings.append(simulation.microphone_signals.copy())
        if use_chirp:
            assert chirp is not None
            emission_time = float(start_times[index])
            analysis_window = time_window_s or (
                emission_time,
                emission_time + float(np.linalg.norm(room_size)) / 343.0 + chirp.size / SAMPLE_RATE,
            )
            onset_detections: tuple[OnsetDetection, ...] = ()
        elif time_window_s is not None:
            analysis_window = time_window_s
            onset_detections: tuple[OnsetDetection, ...] = ()
        elif auto_onset_window:
            analysis_window, onset_detections = shared_onset_window(
                tuple(simulation.microphone_signals),
                SAMPLE_RATE,
                max_delay_s,
                pre_roll_s=pre_roll_s,
                event_duration_s=event_duration_s,
                noise_window_s=onset_noise_window_s,
            )
        else:
            analysis_window = None
            onset_detections = ()
        window_diagnostics.append((analysis_window, onset_detections))
        if use_chirp:
            assert chirp is not None and analysis_window is not None
            emission_time = float(start_times[index])
            noise_window = (
                emission_time - 0.1,
                emission_time - 0.005,
            )
            calibration = localize_chirp_source(
                tuple(simulation.microphone_signals),
                chirp,
                SAMPLE_RATE,
                microphones,
                room_dimensions=room_dimensions_tuple,
                search_window_s=analysis_window,
                noise_window_s=noise_window,
                min_peak_ratio=chirp_min_peak_ratio,
            )
            localization = calibration.localization
        else:
            speech_window = analysis_window or (
                0.0,
                min(len(signal) for signal in simulation.microphone_signals) / SAMPLE_RATE,
            )
            delays = estimate_tdoa_frame_consensus(
                tuple(simulation.microphone_signals),
                SAMPLE_RATE,
                max_delay_s=max_delay_s,
                time_window_s=speech_window,
                frame_duration_s=0.08,
                frame_hop_s=0.04,
                candidate_count=5,
                phat_beta=0.7,
                frequency_band_hz=(300.0, 3_400.0),
            )
            if delays.consensus_fraction is not None:
                microphone_agreement = delays.consensus_fraction[1:]
                print(
                    "        GCC frame agreement: "
                    + ", ".join(f"M{mic + 1}={fraction:.0%}" for mic, fraction in enumerate(microphone_agreement))
                )
                if microphone_agreement and min(microphone_agreement) < 0.5:
                    print("        WARNING: speech TDOA peaks are inconsistent across frames; treat this location as low confidence.")
            localization = solve_position(
                microphones,
                delays,
                room_dimensions=room_dimensions_tuple,
            )
        estimated_position = np.asarray(localization.position, dtype=np.float64)
        position_error = float(np.linalg.norm(estimated_position - actual_position))
        results.append((actual_position.copy(), estimated_position, position_error))


    _print_results(
        results,
        reverberation_time_s,
        snr_db,
        time_window_s,
        window_diagnostics,
        use_chirp,
        auto_onset_window and time_window_s is None,
        used_audio_files,
        used_start_times,
    )
    _plot_results(
        results,
        microphones,
        room_size,
        microphone_recordings,
        window_diagnostics,
        used_start_times,
        SAMPLE_RATE,
        plot_onset_window,
        output_path,
    )
    if show_plot:
        plt.show()
    else:
        plt.close("all")
    return results




def _print_results(
    results: list[tuple[np.ndarray, np.ndarray, float]],
    reverberation_time_s: float | None,
    snr_db: float | None,
    time_window_s: tuple[float, float] | None,
    window_diagnostics: list[
        tuple[tuple[float, float] | None, tuple[OnsetDetection, ...]]
    ],
    use_chirp: bool,
    auto_onset_window: bool,
    used_audio_files: list[str],
    used_start_times: list[float],
) -> None:
    room_mode = "direct path only" if reverberation_time_s is None else f"RT60 {reverberation_time_s:.2f} s"
    noise_mode = "no added noise" if snr_db is None else f"SNR {snr_db:.1f} dB"
    if use_chirp:
        window_mode = "first-arrival chirp matched filtering"
    elif auto_onset_window:
        window_mode = "automatic shared onset window"
    elif time_window_s is None:
        window_mode = "full recording"
    else:
        window_mode = f"manual window {time_window_s[0]:.4f}–{time_window_s[1]:.4f} s"
    print(f"Localization test: {room_mode}, {noise_mode}, {window_mode}")
    print("Target | Start (s) | Actual position (m)       | Estimated position (m)    | Error (m) | Used window (s) | Audio clip")
    print("-" * 158)
    for index, (actual, estimated, error) in enumerate(results):
        actual_text = tuple(round(float(value), 3) for value in actual)
        estimated_text = tuple(round(float(value), 3) for value in estimated)
        window, detections = window_diagnostics[index]
        window_text = "full" if window is None else f"{window[0]:.4f}–{window[1]:.4f}"
        print(
            f"{index:6d} | {used_start_times[index]:9.3f} | "
            f"{str(actual_text):25s} | {str(estimated_text):25s} | "
            f"{error:9.4f} | {window_text:17s} | {used_audio_files[index]}"
        )
        if detections:
            onset_text = ", ".join(
                f"M{mic_index}={detection.onset_time_s:.4f}s"
                for mic_index, detection in enumerate(detections)
            )
            print(f"         detected onsets: {onset_text}")
    errors = [error for _, _, error in results]
    print(f"Mean position error: {np.mean(errors):.4f} m")
    print(f"Maximum position error: {np.max(errors):.4f} m")




def _plot_results(
    results: list[tuple[np.ndarray, np.ndarray, float]],
    microphone_positions: np.ndarray,
    room_dimensions: np.ndarray,
    microphone_recordings: list[np.ndarray],
    window_diagnostics: list[
        tuple[tuple[float, float] | None, tuple[OnsetDetection, ...]]
    ],
    source_start_times_s: list[float],
    sample_rate: int,
    plot_onset_window: bool,
    output_path: Path | None,
) -> None:
    """Show room geometry, per-mic waveforms, a time scrubber, and playback.


    The trial slider chooses which simulated source recording to inspect. The
    time slider moves a shared cursor through all microphone plots. Playback
    outputs the selected microphone channel through the computer's default audio
    device; it is only a local inspection aid, not a beamformed mix.
    """
    n_microphones = microphone_positions.shape[0]
    figure_height = max(8.0, 2.1 * n_microphones + 3.0)
    figure = plt.figure(figsize=(15, figure_height))
    grid = figure.add_gridspec(
        nrows=n_microphones,
        ncols=2,
        width_ratios=(1.0, 1.25),
        left=0.07,
        right=0.97,
        top=0.95,
        bottom=0.24,
        hspace=0.55,
        wspace=0.3,
    )
    room_axes = cast(Any, figure.add_subplot(grid[:, 0], projection="3d"))
    room_axes.set_title("Room layout: actual sources and estimates")


    microphones = microphone_positions
    room_axes.scatter(
        microphones[:, 0], microphones[:, 1], microphones[:, 2],
        marker="^", s=110, color="#1a14c9", label="Phone microphones",
        depthshade=False,
    )
    for index, (x, y, z) in enumerate(microphones):
        room_axes.text(x, y, z, f"  M{index}", color="#1410a3")


    trial_colors = ["#fbb116", "#111111", "#d88a00", "#8f8ff0", "#5b5b6b"]
    for index, (actual, estimated, _) in enumerate(results):
        color = trial_colors[index % len(trial_colors)]
        room_axes.scatter(
            actual[0], actual[1], actual[2], marker="o", s=90,
            color=color, label="_nolegend_", depthshade=False,
        )
        room_axes.scatter(
            estimated[0], estimated[1], estimated[2], marker="x", s=100,
            linewidths=2.5, color=color, label="_nolegend_",
        )
        room_axes.plot(
            (actual[0], estimated[0]),
            (actual[1], estimated[1]),
            (actual[2], estimated[2]),
            color=color, linestyle=":", linewidth=1.5,
        )


    room_axes.set_xlim(0, room_dimensions[0])
    room_axes.set_ylim(0, room_dimensions[1])
    room_axes.set_zlim(0, room_dimensions[2])
    room_axes.set_xlabel("Room X (m)")
    room_axes.set_ylabel("Room Y (m)")
    room_axes.set_zlabel("Height Z (m)")
    room_axes.set_box_aspect(room_dimensions)
    room_axes.legend(
        handles=(
            Line2D([0], [0], marker="^", linestyle="None", color="#1a14c9", label="Phone microphones"),
            Line2D([0], [0], marker="o", linestyle="None", color="#5b5b6b", label="Actual source"),
            Line2D([0], [0], marker="x", linestyle="None", color="#5b5b6b", label="Estimated source"),
        ),
        loc="upper left",
        fontsize="small",
    )


    # Create one waveform axis and moving time cursor for every microphone.
    wave_axes = []
    wave_lines = []
    cursor_lines = []
    emission_lines = []
    window_patches = []
    for mic_index in range(n_microphones):
        axis = figure.add_subplot(grid[mic_index, 1])
        axis.set_ylabel(f"Mic {mic_index}\nAmplitude")
        axis.grid(True, alpha=0.25)
        if mic_index == n_microphones - 1:
            axis.set_xlabel("Time (s)")
        line, = axis.plot([], [], color="#1a14c9", linewidth=0.8)
        cursor = axis.axvline(0.0, color="#111111", linestyle="--", linewidth=1.2)
        emission = axis.axvline(
            0.0,
            color="#d88a00",
            linestyle=":",
            linewidth=1.2,
            alpha=0.85,
            label="Scheduled emission" if mic_index == 0 else "_nolegend_",
        )
        wave_axes.append(axis)
        wave_lines.append(line)
        cursor_lines.append(cursor)
        emission_lines.append(emission)
        window_patches.append(None)


    # Widgets are kept in local variables captured by callbacks; retaining this
    # reference list prevents Matplotlib from garbage-collecting them.
    max_duration_s = max(recording.shape[1] for recording in microphone_recordings) / sample_rate
    trial_axis = figure.add_axes((0.16, 0.16, 0.72, 0.025))
    time_axis = figure.add_axes((0.16, 0.115, 0.72, 0.025))
    mic_axis = figure.add_axes((0.16, 0.07, 0.3, 0.025))
    play_axis = figure.add_axes((0.55, 0.045, 0.15, 0.06))
    status_text = figure.text(0.73, 0.065, "Ready", ha="left", va="center")
    trial_slider = Slider(
        trial_axis,
        "Source trial",
        0,
        max(0, len(results) - 1),
        valinit=0,
        valstep=1,
    )
    time_slider = Slider(
        time_axis,
        "Time (s)",
        0.0,
        max_duration_s,
        valinit=0.0,
    )
    mic_slider = Slider(
        mic_axis,
        "Playback mic",
        0,
        n_microphones - 1,
        valinit=0,
        valstep=1,
    )
    play_button = Button(play_axis, "Play audio")
    widgets = [trial_slider, time_slider, mic_slider, play_button]


    playback = {
        "playing": False,
        "timer_updating": False,
        "start_monotonic": 0.0,
        "start_time_s": 0.0,
    }
    playback_timer = figure.canvas.new_timer(interval=30)


    def stop_playback(message: str = "Playback stopped") -> None:
        if playback["playing"]:
            try:
                import sounddevice as sd
                sd.stop()
            except (ImportError, RuntimeError):
                pass
        playback["playing"] = False
        playback_timer.stop()
        play_button.label.set_text("Play audio")
        status_text.set_text(message)
        figure.canvas.draw_idle()


    def update_waveforms(trial_index: int) -> None:
        recording = microphone_recordings[trial_index]
        times = np.arange(recording.shape[1], dtype=np.float64) / sample_rate
        for mic_index, axis in enumerate(wave_axes):
            wave_lines[mic_index].set_data(times, recording[mic_index])
            emission_lines[mic_index].set_xdata(
                (source_start_times_s[trial_index], source_start_times_s[trial_index])
            )
            axis.set_xlim(0.0, max(float(times[-1]), 1.0 / sample_rate))
            peak = max(float(np.max(np.abs(recording[mic_index]))), 1e-6)
            axis.set_ylim(-1.1 * peak, 1.1 * peak)
            axis.set_title(f"Microphone {mic_index}")
        figure.suptitle(
            f"Trial {trial_index + 1}/{len(results)} — "
            f"actual {tuple(round(float(v), 2) for v in results[trial_index][0])} m, "
            f"estimated {tuple(round(float(v), 2) for v in results[trial_index][1])} m",
            y=0.985,
        )
        update_window_overlay(trial_index)
        update_cursor(time_slider.val)


    def update_window_overlay(trial_index: int) -> None:
        """Shade the shared crop on every mic plot for the selected trial."""
        window = window_diagnostics[trial_index][0]
        for mic_index, axis in enumerate(wave_axes):
            previous_patch = window_patches[mic_index]
            if previous_patch is not None:
                previous_patch.remove()
                window_patches[mic_index] = None
            if plot_onset_window and window is not None:
                label = "Analysis window" if mic_index == 0 else "_nolegend_"
                window_patches[mic_index] = axis.axvspan(
                    window[0],
                    window[1],
                    color="#fbb116",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
        existing_legend = wave_axes[0].get_legend()
        if existing_legend is not None:
            existing_legend.remove()
        wave_axes[0].legend(loc="upper right", fontsize="small", framealpha=0.75)


    def update_cursor(time_s: float) -> None:
        for cursor in cursor_lines:
            cursor.set_xdata((time_s, time_s))
        figure.canvas.draw_idle()


    def on_trial_changed(value: float) -> None:
        if playback["playing"]:
            stop_playback("Trial changed; playback stopped")
        trial_index = int(value)
        trial_window = window_diagnostics[trial_index][0]
        time_slider.set_val(0.0 if trial_window is None else trial_window[0])
        update_waveforms(trial_index)


    def on_time_changed(value: float) -> None:
        update_cursor(value)
        if playback["playing"] and not playback["timer_updating"]:
            stop_playback("Time moved; playback stopped")


    def on_mic_changed(value: float) -> None:
        if playback["playing"]:
            stop_playback("Microphone changed; playback stopped")
        status_text.set_text(f"Selected microphone {int(value)}")
        figure.canvas.draw_idle()


    def advance_playback() -> None:
        elapsed = time.monotonic() - playback["start_monotonic"]
        current_time = playback["start_time_s"] + elapsed
        trial_index = int(trial_slider.val)
        duration_s = microphone_recordings[trial_index].shape[1] / sample_rate
        if current_time >= duration_s:
            time_slider.set_val(duration_s)
            stop_playback("Playback finished")
            return
        playback["timer_updating"] = True
        time_slider.set_val(current_time)
        playback["timer_updating"] = False


    def on_play_clicked(_event: object) -> None:
        if playback["playing"]:
            stop_playback("Playback stopped")
            return
        try:
            import sounddevice as sd
        except ImportError:
            status_text.set_text("Install sounddevice to enable audio playback")
            figure.canvas.draw_idle()
            return


        trial_index = int(trial_slider.val)
        mic_index = int(mic_slider.val)
        start_sample = min(
            int(time_slider.val * sample_rate),
            microphone_recordings[trial_index].shape[1] - 1,
        )
        audio = microphone_recordings[trial_index][mic_index, start_sample:]
        try:
            sd.play(audio, samplerate=sample_rate, blocking=False)
        except Exception as error:  # no default output device or unsupported audio setup
            status_text.set_text(f"Audio playback unavailable: {error}")
            figure.canvas.draw_idle()
            return


        playback["playing"] = True
        playback["start_monotonic"] = time.monotonic()
        playback["start_time_s"] = start_sample / sample_rate
        play_button.label.set_text("Stop audio")
        status_text.set_text(f"Playing source {trial_index + 1}, microphone {mic_index}")
        playback_timer.start()


    trial_slider.on_changed(on_trial_changed)
    time_slider.on_changed(on_time_changed)
    mic_slider.on_changed(on_mic_changed)
    play_button.on_clicked(on_play_clicked)
    playback_timer.add_callback(advance_playback)
    initial_window = window_diagnostics[0][0]
    if initial_window is not None:
        time_slider.set_val(initial_window[0])
    update_waveforms(0)
    widgets.append(playback_timer)
    # Keep widget instances alive for the lifetime of the interactive figure.
    setattr(figure, "_visualizer_widgets", widgets)
    # Reserve the bottom area for the sliders and playback controls.
    figure.subplots_adjust(bottom=0.24, top=0.93, left=0.08, right=0.97)


    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_path, dpi=160, bbox_inches="tight")
        print(f"Plot saved to: {output_path}")




def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--room-dimensions",
        type=_parse_3d_point,
        default=ROOM_DIMENSIONS,
        metavar="X,Y,Z",
        help="Room size in meters (default: 5,4,3).",
    )
    parser.add_argument(
        "--mic",
        type=_parse_3d_point,
        action="append",
        default=None,
        metavar="X,Y,Z",
        help="Phone microphone position in meters; repeat once per phone. Defaults to the built-in layout.",
    )
    parser.add_argument(
        "--source",
        type=_parse_3d_point,
        action="append",
        default=None,
        metavar="X,Y,Z",
        help="Known test-source position in meters; repeat once per target. Defaults to the built-in targets.",
    )
    parser.add_argument(
        "--source-gap-s",
        type=float,
        default=0.75,
        help="Default time spacing between test-source events in seconds (default: 0.75).",
    )
    parser.add_argument(
        "--source-start-s",
        type=float,
        action="append",
        default=None,
        help="Explicit source start time in seconds; repeat once per --source, in matching order.",
    )
    parser.add_argument(
        "--rt60",
        type=float,
        default=None,
        help="Enable room reflections with this target RT60 in seconds (default: direct path only).",
    )
    parser.add_argument(
        "--snr-db",
        type=float,
        default=None,
        help="Add simulated microphone noise at this SNR in dB.",
    )
    parser.add_argument(
        "--window-start-s",
        type=float,
        default=None,
        help="Shared recording-time window start in seconds (use with --window-end-s).",
    )
    parser.add_argument(
        "--window-end-s",
        type=float,
        default=None,
        help="Shared recording-time window end in seconds (use with --window-start-s).",
    )
    parser.add_argument(
        "--pre-roll-ms",
        type=float,
        default=5.0,
        help="Audio retained before the earliest detected onset (default: 5 ms).",
    )
    parser.add_argument(
        "--event-duration-ms",
        type=float,
        default=500.0,
        help="Capture duration after the farthest expected arrival (default: 500 ms).",
    )
    parser.add_argument(
        "--onset-noise-start-s",
        type=float,
        default=None,
        help="Start of known quiet interval for onset calibration (use with --onset-noise-end-s).",
    )
    parser.add_argument(
        "--onset-noise-end-s",
        type=float,
        default=None,
        help="End of known quiet interval for onset calibration (use with --onset-noise-start-s).",
    )
    parser.add_argument(
        "--speech-dataset-dir",
        type=Path,
        default=DEFAULT_SPEECH_DATASET,
        help="Extracted LibriSpeech directory containing FLAC/WAV clips.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed random speech-clip selection and noise for repeatable runs.",
    )
    parser.add_argument(
        "--chirp",
        action="store_true",
        help="Use a short calibration chirp and first-arrival matched filtering instead of speech GCC-PHAT.",
    )
    parser.add_argument(
        "--chirp-min-peak-ratio",
        type=float,
        default=0.05,
        help="Minimum matched-filter peak as a fraction of the strongest candidate (default: 0.05).",
    )
    parser.add_argument(
        "--full-recording",
        action="store_true",
        help="Disable automatic onset detection and analyze each full recording.",
    )
    parser.add_argument(
        "--plot-onset-window",
        action="store_true",
        help="Shade the chirp arrival-search or speech analysis window on each microphone waveform plot.",
    )
    parser.add_argument(
        "--save-only",
        action="store_true",
        help="Save the plot without opening a GUI window.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("localization_test.png"),
        help="Plot output path (default: localization_test.png in current directory).",
    )
    args = parser.parse_args()
    if (args.window_start_s is None) != (args.window_end_s is None):
        parser.error("--window-start-s and --window-end-s must be provided together")
    if args.full_recording and args.window_start_s is not None:
        parser.error("--full-recording cannot be combined with manual window options")
    if (args.onset_noise_start_s is None) != (args.onset_noise_end_s is None):
        parser.error(
            "--onset-noise-start-s and --onset-noise-end-s must be provided together"
        )
    time_window_s = (
        None
        if args.window_start_s is None
        else (args.window_start_s, args.window_end_s)
    )
    if args.source_start_s is not None and len(args.source_start_s) != len(
        args.source if args.source is not None else SOURCE_POSITIONS
    ):
        parser.error("provide exactly one --source-start-s value per --source")
    onset_noise_window_s = (
        None
        if args.onset_noise_start_s is None
        else (args.onset_noise_start_s, args.onset_noise_end_s)
    )


    run_visual_test(
        room_dimensions=args.room_dimensions,
        microphone_positions=np.asarray(args.mic if args.mic is not None else MICROPHONE_POSITIONS),
        source_positions=np.asarray(args.source if args.source is not None else SOURCE_POSITIONS),
        reverberation_time_s=args.rt60,
        snr_db=args.snr_db,
        time_window_s=time_window_s,
        source_start_times_s=(
            np.asarray(args.source_start_s, dtype=np.float64)
            if args.source_start_s is not None
            else None
        ),
        source_gap_s=args.source_gap_s,
        chirp_min_peak_ratio=args.chirp_min_peak_ratio,
        auto_onset_window=not args.full_recording,
        pre_roll_s=args.pre_roll_ms / 1_000.0,
        event_duration_s=args.event_duration_ms / 1_000.0,
        onset_noise_window_s=onset_noise_window_s,
        speech_dataset_dir=args.speech_dataset_dir,
        use_chirp=args.chirp,
        random_seed=args.seed,
        plot_onset_window=args.plot_onset_window,
        show_plot=not args.save_only,
        output_path=args.output,
    )




def _find_speech_files(dataset_dir: Path) -> list[Path]:
    """Recursively list supported audio files in an extracted corpus folder."""
    if not dataset_dir.is_dir():
        return []
    return sorted(
        path
        for path in dataset_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".flac", ".wav"}
    )




def _load_audio_mono(audio_path: Path, target_sample_rate: int) -> np.ndarray:
    """Read an audio clip, mix channels to mono, and resample if required."""
    audio, sample_rate = sf.read(audio_path, dtype="float64", always_2d=True)
    mono = np.mean(audio, axis=1)
    if mono.size == 0 or not np.all(np.isfinite(mono)):
        raise ValueError(f"Audio clip is empty or non-finite: {audio_path}")
    if sample_rate != target_sample_rate:
        common_divisor = int(np.gcd(sample_rate, target_sample_rate))
        mono = resample_poly(
            mono,
            target_sample_rate // common_divisor,
            sample_rate // common_divisor,
        )
    return np.asarray(mono, dtype=np.float64)




def _parse_3d_point(value: str) -> tuple[float, float, float]:
    """Parse one comma-separated XYZ coordinate from a CLI argument."""
    try:
        coordinates = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("coordinates must be numeric, e.g. 1.0,2.0,1.5") from error
    if len(coordinates) != 3 or not np.all(np.isfinite(coordinates)):
        raise argparse.ArgumentTypeError("coordinates must be three finite values: X,Y,Z")
    return coordinates




if __name__ == "__main__":
    main()



