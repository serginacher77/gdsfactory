from __future__ import annotations

from collections.abc import Callable
from typing import Any

import kfactory as kf
import numpy as np
from kfactory.routing.optical import OpticalManhattanRoute
from numpy import float64, ndarray

import gdsfactory as gf
from gdsfactory.components.bend_euler import bend_euler
from gdsfactory.components.straight import straight as straight_function
from gdsfactory.functions import remove_identicals
from gdsfactory.port import Port
from gdsfactory.routing.get_route import place_route
from gdsfactory.routing.manhattan import (
    generate_manhattan_waypoints,
    remove_flat_angles,
)
from gdsfactory.routing.route_ports_to_side import route_ports_to_side
from gdsfactory.routing.validation import validate_connections
from gdsfactory.typings import ComponentSpec, Route


def _groups(
    ports: list[Port], cut: float64, axis: str = "X"
) -> tuple[list[Port], list[Any]] | tuple[list[Port], list[Port]]:
    if axis == "Y":
        group1 = [p for p in ports if p.x <= cut]
        group2 = [p for p in ports if p.x > cut]
    else:
        group1 = [p for p in ports if p.y <= cut]
        group2 = [p for p in ports if p.y > cut]
    return group1, group2


def get_bundle_udirect(
    component: ComponentSpec,
    ports1: list[Port],
    ports2: list[Port],
    separation: float = 5.0,
    start_straight_length: float = 0.01,
    end_straight_length: float = 0.01,
    bend: ComponentSpec = bend_euler,
    straight=straight_function,
    path_length_match_loops: int | None = None,
    path_length_match_extra_length: float = 0.0,
    path_length_match_modify_segment_i: int = -2,
    enforce_port_ordering: bool = True,
    cross_section: str = "xs_sc",
    with_markers: bool = False,
    **kwargs,
) -> list[OpticalManhattanRoute]:
    r"""Returns list of routes.

    Args:
        ports1: list of start ports.
        ports2: list of end ports.
        separation: between straights.
        start_straight_length: in um.
        end_straight_length: in um.
        bend: bend spec.
        path_length_match_loops: Integer number of loops to add to bundle
            for path length matching (won't try to match if None).
        path_length_match_extra_length: Extra length to add
            to path length matching loops (requires path_length_match_loops != None).
        path_length_match_modify_segment_i: Index of straight segment to add path
            length matching loops to (requires path_length_match_loops != None).
        enforce_port_ordering: If True, enforce that the ports are connected in the specific order.

    Returns:
        list of optical routes.


    Used for routing multiple ports back to a bundled input in a component

    ::

        X: start ports
        D: End ports

        On this example below, the axis is along X

                           X------\
                                  |
                           X----\ |
                          ...   | |
                           X--\ | |
                              | | |
          D-------------------/ | |
          ...                   | |
          D---------------------/ |
          D-----------------------
          D-----------------------\
          D---------------------\ |
          ...                   | |
          D-------------------\ | |
                              | | |
                           X--/ | |
                          ...   | |
                           X----/ |
                                  |
                           X------/
    """
    _p1, _p2 = ports1.copy(), ports2.copy()

    routes = _get_bundle_udirect_waypoints(
        ports1,
        ports2,
        separation=separation,
        start_straight_length=start_straight_length,
        end_straight_offset=end_straight_length,
        routing_func=generate_manhattan_waypoints,
        bend=bend,
    )
    # if path_length_match_loops:
    #     routes = [np.array(route) for route in routes]
    #     routes = path_length_matched_points(
    #         routes,
    #         extra_length=path_length_match_extra_length,
    #         bend=bend,
    #         nb_loops=path_length_match_loops,
    #         modify_segment_i=path_length_match_modify_segment_i,
    #         # cross_section=cross_section,
    #         **kwargs,
    #     )

    r = []
    for route in routes:
        port1 = next(
            filter(lambda port: kf.kdb.Point(*port.center) == route[0], ports1)
        )
        port2 = next(
            filter(lambda port: kf.kdb.Point(*port.center) == route[-1], ports2)
        )
        if with_markers:
            marker = gf.components.rectangle(size=(1, 1), layer=(2, 0), centered=True)

            for point in route:
                ref = component.add_ref(marker)
                ref.center = point

        route = place_route(
            component=component,
            port1=port1,
            port2=port2,
            waypoints=route,
            bend=bend,
            straight=straight,
            cross_section=cross_section,
            **kwargs,
        )
        r.append(route)

    # if enforce_port_ordering:
    #     return validate_connections(_p1, _p2, r)
    return r


def _get_bundle_udirect_waypoints(
    ports1: list[Port],
    ports2: list[Port],
    routing_func: Callable = generate_manhattan_waypoints,
    separation: float = 5.0,
    start_straight_length: float = 0.01,
    end_straight_length: float = 0.01,
    end_straight_offset: float = 0.0,
    start_straight_offset: float = 0.0,
    bend: ComponentSpec = bend_euler,
) -> list[ndarray]:
    """Returns list of routes.

    Args:
        ports1: list of start ports.
        ports2: list of end ports.
        routing_func: filter to apply to the manhattan waypoints
        separation: between straights.
        start_straight_length: in um.
        end_straight_length: in um.
        start_straight_offset: in um.
        bend: bend spec.

    """
    nb_ports = len(ports1)

    if len(ports2) != nb_ports:
        raise ValueError(
            "Number of start ports should match number of end ports."
            f"Got {len(ports1)} {len(ports2)}"
        )
    if len({p.orientation for p in ports1 + ports2}) > 1:
        orientations1 = [p.orientation for p in ports1]
        orientations2 = [p.orientation for p in ports2]
        raise ValueError(
            "All ports should have the same orientation. "
            f"Got \n{orientations1}\n{orientations2}"
        )

    xs_end = [p.x for p in ports2]
    ys_end = [p.y for p in ports2]

    x_cut = 0.5 * (min(xs_end) + max(xs_end))
    y_cut = 0.5 * (min(ys_end) + max(ys_end))

    # Find axis
    angle_start = ports1[0].orientation

    if angle_start in [0, 180]:
        axis = "X"
        cut = y_cut
    else:
        axis = "Y"
        cut = x_cut

    # Get groups (below, above) or (left, right)
    group1, group2 = _groups(ports1, cut, axis=axis)

    # Sort ports to make them easy to connect
    if axis == "X":
        group1.sort(key=lambda p: -p.y)
        group2.sort(key=lambda p: p.y)

        ports2.sort(key=lambda p: p.y)
        end_group1 = ports2[: len(group1)]
        end_group2 = ports2[len(group1) :]
        end_group2.sort(key=lambda p: -p.y)

        xs_start = [p.x for p in ports1]

        if angle_start == 0:
            dx = xs_start[0] - xs_end[0]
        elif angle_start == 180:
            dx = xs_end[0] - xs_start[0]
        end_straight_length = max(end_straight_length, dx)

    elif axis == "Y":
        group1.sort(key=lambda p: -p.x)
        group2.sort(key=lambda p: p.x)

        ports2.sort(key=lambda p: p.x)
        end_group1 = ports2[: len(group1)]
        end_group2 = ports2[len(group1) :]
        end_group2.sort(key=lambda p: -p.x)

        ys_start = [p.y for p in ports1]

        if angle_start == 90:
            dy = ys_start[0] - ys_end[0]
        elif angle_start == 270 or angle_start is None:
            dy = ys_end[0] - ys_start[0]
        end_straight_length = max(end_straight_length, dy)

    # add offsets
    start_straight_length += start_straight_offset
    end_straight_length += end_straight_offset

    connections = []
    straight_len_end = end_straight_length
    straight_len_start = start_straight_length
    for p_start, p_end in zip(group1, end_group1):
        _c = routing_func(
            p_start,
            p_end,
            start_straight_length=straight_len_start,
            end_straight_length=straight_len_end,
            bend=bend,
        )
        connections += [_c]
        straight_len_end += separation
        straight_len_start += separation

    straight_len_end = end_straight_length
    straight_len_start = start_straight_length
    for p_start, p_end in zip(group2, end_group2):
        _c = routing_func(
            p_start,
            p_end,
            start_straight_length=straight_len_start,
            end_straight_length=straight_len_end,
            bend=bend,
        )
        connections += [_c]
        straight_len_end += separation
        straight_len_start += separation

    return connections


def get_bundle_uindirect(
    component: ComponentSpec,
    ports1: list[Port],
    ports2: list[Port],
    route_filter: Callable = place_route,
    separation: float = 5.0,
    extension_length: float = 0.0,
    start_straight_length: float = 0.01,
    end_straight_length: float = 0.01,
    enforce_port_ordering: bool = True,
    **routing_params,
) -> list[Route]:
    r"""Returns list of routes.

    Args:
        component: component to add the routes to.
        ports1: list of start ports.
        ports2: list of end ports.
        route_filter: filter to apply to the manhattan waypoints
            e.g `get_route_from_waypoints` for deep etch strip straight
        separation: center to center waveguide spacing.
        extension_length: in um.
        start_straight_length: extends in um.
        end_straight_length: in um.

    Returns:
        list of routes, where each route has references, ports and length.


    Used for routing multiple ports back to a bundled input in a component


    ::

        X: start ports
        D: End ports


                                    X------
                                    X----  |
                                   ...   | |
                                    X--\ | |
                                       | | |
            /--------------------------/ | |
            |                            | |
            | /--------------------------/ |
            | |                            |
            | | /--------------------------/
            | | |
            | | \--D
            | \----D
            |     ...
            \------D
            /------D
            |     ...
            | /----D
            | | /--D
            | | |
            | | \--------------------------
            | |                            |
            | \--------------------------\ |
            |                            | |
            \--------------------------\ | |
                                       | | |
                                    X--/ | |
                                   ...   | |
                                    X----/ |
                                    X------/
        '''

    """
    _p1, _p2 = ports1.copy(), ports2.copy()
    routes = _get_bundle_uindirect_waypoints(
        ports1,
        ports2,
        separation=separation,
        start_straight_length=start_straight_length,
        end_straight_length=end_straight_length,
        routing_func=generate_manhattan_waypoints,
        extension_length=extension_length,
        **routing_params,
    )

    routes = [route_filter(route, **routing_params) for route in routes]
    if enforce_port_ordering:
        routes = validate_connections(_p1, _p2, routes)
    return routes


def _get_bundle_uindirect_waypoints(
    ports1: list[Port],
    ports2: list[Port],
    routing_func: Callable = generate_manhattan_waypoints,
    separation: float = 5.0,
    extension_length: float = 0.0,
    start_straight_length: float = 0.01,
    end_straight_length: float = 0.01,
    **routing_func_params,
) -> list[ndarray]:
    nb_ports = len(ports1)
    ports1 = ports1.copy()
    ports2 = ports2.copy()

    if len(ports2) != nb_ports:
        raise ValueError(
            "Number of start ports should match number of end ports."
            "Got {} {}".format(len(ports1), len(ports2))
        )

    if len({p.orientation for p in ports1}) > 1:
        raise ValueError(f"All start port angles should be the same. Got {ports1}")

    if len({p.orientation for p in ports2}) > 1:
        raise ValueError(f"All end port angles should be the same. Got {ports2}")

    xs_end = [p.x for p in ports2]
    ys_end = [p.y for p in ports2]

    # Compute the bundle axis
    axis = "X" if ports1[0].orientation in [0, 180] else "Y"
    # Split start ports in two groups:
    #    - the ones on the south/west of end ports (depending on bundle axis)
    #    - the ones on the north/east of end ports (depending on bundle axis)

    if axis == "X":
        y_cut = 0.5 * (min(ys_end) + max(ys_end))
        group1 = [p for p in ports1 if p.y <= y_cut]
        group2 = [p for p in ports1 if p.y > y_cut]

        if ports1[0].orientation == 0 and ports2[0].orientation == 180:
            """X->

            <-D
                 X->

            """
            # To go back to a U bundle
            group1_route_directives = ["north", "west"]
            group2_route_directives = ["south", "west"]

        elif ports1[0].orientation == 180 and ports2[0].orientation == 0:
            """
            <-X
                 D->
            <-X
            """
            # To go back to a U bundle
            group1_route_directives = ["north", "east"]
            group2_route_directives = ["south", "east"]

        else:
            print("u_undirect_bundle not designed to work in this case")

    if axis == "Y":
        x_cut = 0.5 * (min(xs_end) + max(xs_end))
        group1 = [p for p in ports1 if p.x <= x_cut]
        group2 = [p for p in ports1 if p.x > x_cut]

        if ports1[0].orientation == 90 and ports2[0].orientation == 270:
            """

            ^     ^
            |     |
            X     X
               D
               |

            """
            # To go back to a U bundle
            group1_route_directives = ["east", "south"]
            group2_route_directives = ["west", "south"]

        elif ports1[0].orientation == 270 and ports2[0].orientation == 90:
            """
               ^
               |
               D
            X     X
            |     |

            """
            # To go back to a U bundle
            group1_route_directives = ["east", "north"]
            group2_route_directives = ["west", "north"]

        else:
            print("u_undirect_bundle not designed to work in this case")

    # Do the routing directives to get back to a u_bundle direct case

    routing_param = {
        "routing_func": routing_func,
        "separation": separation,
        **routing_func_params,
    }

    # Multiple sections of different routes are generated in different places.
    # At the output, we want a list of routes. (not a list of portions of route)
    # dict_connections keeps track of these sections

    dict_connections = {i: [] for i in range(nb_ports)}

    def add_connections(conns) -> None:
        """Adds connections.

        Ensures that each section in a batch of connection. is added to
        the correct route. Also we don't know in which order the routes
        are given (from beginning to end or vice versa)

        """
        end_prev_conns = [(k, v[-1][-1]) for k, v in dict_connections.items()]
        for c in conns:
            p = c[0]
            for i, q in end_prev_conns:
                if np.abs(p - q).sum() < 1e-9:
                    dict_connections[i] += [c]
                    break

    # First part
    # print(group1_route_directives)
    conn1, tmp_ports1 = route_ports_to_side(
        group1,
        group1_route_directives[0],
        extension_length=extension_length,
        **routing_param,
    )

    conn2, tmp_ports2 = route_ports_to_side(
        group2,
        group2_route_directives[0],
        extension_length=extension_length,
        **routing_param,
    )
    conn = conn1 + conn2
    dict_connections = {i: [c] for i, c in enumerate(conn)}

    # Second part
    conn1, tmp_ports1 = route_ports_to_side(
        tmp_ports1, group1_route_directives[1], **routing_param
    )

    conn2, tmp_ports2 = route_ports_to_side(
        tmp_ports2, group2_route_directives[1], **routing_param
    )

    add_connections(conn1 + conn2)

    bundle_params = {
        **routing_param,
        "start_straight_length": start_straight_length,
        "end_straight_length": end_straight_length,
    }

    ports2.sort(key=lambda p: p.y)
    conns = []
    if tmp_ports1:
        conn1 = _get_bundle_udirect_waypoints(
            tmp_ports1, ports2[: len(tmp_ports1)], **bundle_params
        )
        conns.append(conn1)
    if tmp_ports2:
        conn2 = _get_bundle_udirect_waypoints(
            tmp_ports2, ports2[len(tmp_ports1) :], **bundle_params
        )
        conns.append(conn2)
    if len(conns) > 1:
        add_connections(conn1 + conn2)
    elif len(conns) == 1:
        add_connections(conns[0])
    else:
        raise ValueError("No connections generated!")

    def _merge_connections(list_of_points):
        a = [list_of_points[0]]
        a += [point[1:] for point in list_of_points[1:]]
        b = np.vstack(a)
        b = remove_identicals(b)
        b = remove_flat_angles(b)
        return b

    connections = [_merge_connections(c) for c in dict_connections.values()]
    return connections


if __name__ == "__main__":
    # import gdsfactory as gf

    # c = gf.Component("demo")
    # c1 = c << gf.components.mmi2x2()
    # c2 = c << gf.components.mmi2x2()
    # c2.d.move((100, 40))
    # routes = gf.routing.place_bundle(
    #     c,
    #     [c1.ports["o2"], c1.ports["o1"]],
    #     [c2.ports["o1"], c2.ports["o2"]],
    #     enforce_port_ordering=False,
    #     # start_straight_length=0.001,
    #     # end_straight_length=0.01,
    #     # layer=(2, 0),
    #     # straight=partial(gf.components.straight, layer=(2, 0), width=1),
    # )

    dy = 200
    orientation = 270
    layer = (1, 0)
    xs1 = [-100, -90, -80, -55, -35, 24, 0] + [200, 210, 240]
    axis = "X" if orientation in [0, 180] else "Y"
    pitch = 10.0
    N = len(xs1)
    xs2 = [70 + i * pitch for i in range(N)]

    if axis == "X":
        ports1 = [
            Port(
                f"top_{i}",
                center=(0, xs1[i]),
                width=0.5,
                orientation=orientation,
                layer=layer,
            )
            for i in range(N)
        ]

        ports2 = [
            Port(
                f"bottom_{i}",
                center=(dy, xs2[i]),
                width=0.5,
                orientation=orientation,
                layer=layer,
            )
            for i in range(N)
        ]

    else:
        ports1 = [
            Port(
                f"top_{i}",
                center=(xs1[i], 0),
                width=0.5,
                orientation=orientation,
                layer=layer,
            )
            for i in range(N)
        ]

        ports2 = [
            Port(
                f"bottom_{i}",
                center=(xs2[i], dy),
                width=0.5,
                orientation=orientation,
                layer=layer,
            )
            for i in range(N)
        ]

    c = gf.Component()
    routes = gf.routing.place_bundle(
        c, ports1, ports2, radius=10.0, enforce_port_ordering=False
    )
    c.add_ports(ports1)
    c.add_ports(ports2)
    c.show()
