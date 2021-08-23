from typing import Dict, Optional, Union

from gdsfactory.cell import cell
from gdsfactory.component import Component
from gdsfactory.components.bend_euler import bend_euler
from gdsfactory.components.mmi1x2 import mmi1x2
from gdsfactory.components.mzi_arm import mzi_arm
from gdsfactory.components.straight import straight as straight_function
from gdsfactory.types import ComponentFactory, ComponentOrFactory, Layer


@cell
def mzi(
    delta_length: float = 10.0,
    length_y: float = 0.8,
    length_x: float = 0.1,
    bend: ComponentOrFactory = bend_euler,
    straight: ComponentFactory = straight_function,
    straight_y: Optional[ComponentFactory] = None,
    straight_horizontal_top: Optional[ComponentFactory] = None,
    straight_horizontal_bot: Optional[ComponentFactory] = None,
    splitter: ComponentOrFactory = mmi1x2,
    combiner: Optional[ComponentFactory] = None,
    with_splitter: bool = True,
    splitter_settings: Optional[Dict[str, Union[int, float]]] = None,
    combiner_settings: Optional[Dict[str, Union[int, float]]] = None,
    layer: Optional[Layer] = None,
    **kwargs,
) -> Component:
    """Mzi.

    Args:
        delta_length: bottom arm vertical extra length
        length_y: vertical length for both and top arms
        length_x: horizontal length
        bend: 90 degrees bend library
        straight: straight function
        straight_y: straight for length_y and delta_length
        straight_horizontal_top: straight for length_x
        straight_horizontal_bot: straight for length_x
        splitter: splitter function
        combiner: combiner function
        with_splitter: if False removes splitter
        splitter_settings:
        combiner_settings:
        kwargs: cross_section settings

    .. code::

                   __Lx__
                  |      |
                  Ly     Lyr (not a parameter)
                  |      |
        splitter==|      |==combiner
                  |      |
                  Ly     Lyr (not a parameter)
                  |      |
                  | delta_length/2
                  |      |
                  |__Lx__|

            ____________           __________
            |          |          |
            |          |       ___|
        ____|          |____
            |            d1     d2
        ____|           ____
            |          |       ____
            |          |          |
            |__________|          |__________
    """
    combiner = combiner or splitter

    splitter_settings = splitter_settings or {}
    combiner_settings = combiner_settings or {}

    c = Component()
    cp1 = splitter(**splitter_settings, **kwargs) if callable(splitter) else splitter
    cp2 = combiner(**combiner_settings, **kwargs) if combiner else cp1

    cin = c << cp1
    cout = c << cp2

    ports_cp1 = cp1.get_ports_list(clockwise=False)
    ports_cp2 = cp2.get_ports_list(clockwise=False)
    layer = layer or ports_cp1[0].layer

    port_e1_cp1 = ports_cp1[1]
    port_e0_cp1 = ports_cp1[0]

    port_e1_cp2 = ports_cp2[1]
    port_e0_cp2 = ports_cp2[0]

    y1t = port_e1_cp1.y
    y1b = port_e0_cp1.y

    y2t = port_e1_cp2.y
    y2b = port_e0_cp2.y

    d1 = abs(y1t - y1b)  # splitter ports distance
    d2 = abs(y2t - y2b)  # combiner ports distance

    if d2 > d1:
        length_y_left = length_y + (d2 - d1) / 2
        length_y_right = length_y
    else:
        length_y_right = length_y + (d1 - d2) / 2
        length_y_left = length_y

    top_arm = c << mzi_arm(
        straight_x=straight_horizontal_top,
        straight_y=straight_y,
        length_x=length_x,
        length_y_left=length_y_left,
        length_y_right=length_y_right,
        bend=bend,
        **kwargs,
    )
    bot_arm = c << mzi_arm(
        straight_x=straight_horizontal_bot,
        straight_y=straight_y,
        length_x=length_x,
        length_y_left=length_y_left + delta_length / 2,
        length_y_right=length_y_right + delta_length / 2,
        bend=bend,
        **kwargs,
    )

    bot_arm.mirror()
    top_arm.connect("o1", port_e1_cp1)
    bot_arm.connect("o1", port_e0_cp1)
    cout.connect(port_e1_cp2.name, bot_arm.ports["o2"])
    c.add_ports(cin.get_ports_list(orientation=180), prefix="in")
    c.add_ports(cout.get_ports_list(orientation=0), prefix="out")

    c.add_ports(top_arm.get_ports_list(port_type="electrical"), prefix="top")
    c.add_ports(bot_arm.get_ports_list(port_type="electrical"), prefix="bot")

    c.auto_rename_ports()
    return c


if __name__ == "__main__":
    import gdsfactory as gf

    # delta_length = 116.8 / 2
    # print(delta_length)
    # c = mzi(delta_length=delta_length, with_splitter=False)
    # c.pprint_netlist()
    # mmi2x2 = gf.partial(gf.c.mmi2x2, width_mmi=5, gap_mmi=2)
    # c = mzi(delta_length=10, combiner=gf.c.mmi1x2, splitter=mmi2x2)

    c = mzi(
        delta_length=100,
        straight_horizontal_top=gf.c.straight_heater_metal,
        straight_horizontal_bot=gf.c.straight_heater_metal,
        length_x=50,
        length_y=1.8,
    )
    c.show(show_ports=True)
    # c.pprint()
    # n = c.get_netlist()
    # c.plot()
    # print(c.get_settings())
