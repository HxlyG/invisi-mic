import matplotlib.pyplot as plt
import numpy as np
import pyroomacoustics as pra

def get_materials():
    return pra.parameters.materials_absorption_table.keys()

def add_mics(mic_positions: list[list[float]], room: pra.Room):
    for mic in mic_positions:
        room.add_microphone(mic)

def add_sources(talker_positions: list[list[float]], room: pra.Room):
    for talker in talker_positions:
        room.add_source(talker)

def shoebox_simulation(shoebox_dims, mic_positions, talker_positions: list[list[float]]):
    room = pra.ShoeBox(shoebox_dims)

    add_sources(talker_positions, room)
    add_mics(mic_positions, room)

    # plot the room and resulting beamformer
    fig, ax = room.plot(
        freq=[1000, 2000, 4000, 8000], img_order=0, mic_marker_size=30
    )

    xs = [mic[0] for mic in mic_positions]
    ys = [mic[1] for mic in mic_positions]

    if room.dim == 2:
        ax.scatter(
            xs,
            ys,
            s=80,
            c="red",
            marker="o",
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
            label="microphones",
        )
    else:
        zs = [mic[2] for mic in mic_positions]
        ax.scatter(
            xs,
            ys,
            zs,
            s=80,
            c="red",
            marker="o",
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
            label="microphones",
        )

    ax.legend(loc="upper right")

    room.compute_rir()
    rir_fig, rir_axes = room.plot_rir(kind="ir")

    plt.show()
    plt.close(fig)
    plt.close(rir_fig)