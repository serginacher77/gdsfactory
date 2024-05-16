"""Containers are Pcells that contain another Pcell."""

from functools import partial

import gdsfactory as gf

pad_spacing = 100
fiber_spacing = 127


add_fiber_array_optical_south_electrical_north = partial(
    gf.c.add_fiber_array_optical_south_electrical_north,
    pad=gf.c.pad,
    with_loopback=True,
    pad_spacing=pad_spacing,
)


if __name__ == "__main__":
    c = add_fiber_array_optical_south_electrical_north()
