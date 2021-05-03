from typing import Optional

import pp
from pp.component import Component
from pp.components.bezier import bezier
from pp.cross_section import strip
from pp.types import CrossSectionFactory


@pp.cell
def bend_s(
    height: float = 2.0,
    length: float = 10.0,
    nb_points: int = 99,
    cross_section_factory: Optional[CrossSectionFactory] = None,
    **cross_section_settings,
) -> Component:
    """S bend with bezier curve

    Args:
        height: in y direction
        length: in x direction
        layer: gds number
        nb_points: number of points
        cross_section_factory
        **cross_section_settings

    .. plot::
      :include-source:

      import pp

      c = pp.components.bend_s(height=20)
      c.plot()

    """
    l, h = length, height
    cross_section_factory = cross_section_factory or strip
    cross_section = cross_section_factory(**cross_section_settings)
    width = cross_section.info["width"]
    layer = cross_section.info["layer"]

    c = bezier(
        width=width,
        control_points=[(0, 0), (l / 2, 0), (l / 2, h), (l, h)],
        npoints=nb_points,
        layer=layer,
    )
    c.add_port(name="W0", port=c.ports.pop("0"))
    c.add_port(name="E0", port=c.ports.pop("1"))

    return c


if __name__ == "__main__":
    c = bend_s(width=1)
    c.pprint()
    # c = bend_s_biased()
    # print(c.info["min_bend_radius"])
    c.show()
