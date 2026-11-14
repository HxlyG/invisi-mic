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
    fig, _ = room.plot(freq=[1000, 2000, 4000, 8000], img_order=0)
    plt.show()
    plt.close(fig)