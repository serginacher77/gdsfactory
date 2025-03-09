from __future__ import annotations

import gdsfactory as gf
from gdsfactory.path import extrude_transition, spiral_archimedean, transition
from gdsfactory.typings import CrossSectionSpec


@gf.cell
def terminator_spiral(
    separation: float = 2.0,
    cross_section: CrossSectionSpec = "strip",
    cross_section_tip: CrossSectionSpec | None = None,
    width_tip: float = 0.2,
    number_of_loops: float = 1,
    npoints: int = 1000,
    min_bend_radius: float | None = None,
) -> gf.Component:
    """Returns doped taper to terminate waveguides.

    Args:
        separation: separation between the loops.
        cross_section: input cross-section.
        cross_section_tip: cross-section at the end of the termination.
        width_tip: width of the default cross-section at the end of the termination.
            Only used if cross_section_tip is not None.
        number_of_loops: number of loops in the spiral.
        npoints: points for the spiral.
        min_bend_radius: minimum bend radius for the spiral.
    """
    cross_section = gf.get_cross_section(cross_section)

    cross_section_tip = cross_section_tip or gf.get_cross_section(
        cross_section, width=width_tip
    )

    xs = transition(
        cross_section1=cross_section,
        cross_section2=cross_section_tip,
        width_type="linear",
    )

    min_bend_radius = min_bend_radius or cross_section.radius_min
    assert min_bend_radius

    path = spiral_archimedean(
        min_bend_radius=min_bend_radius,
        separation=separation,
        number_of_loops=number_of_loops,
        npoints=npoints,
    )
    path.start_angle = 0
    path.end_angle = 0

    return extrude_transition(path, transition=xs)


if __name__ == "__main__":
    c = terminator_spiral()
    c.show()
