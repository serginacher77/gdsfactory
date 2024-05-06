from __future__ import annotations

import shapely

from gdsfactory.component import Component
from gdsfactory.technology import LayerStack, LayerViews
from gdsfactory.typings import Layer


def to_3d(
    component: Component,
    layer_views: LayerViews | None = None,
    layer_stack: LayerStack | None = None,
    exclude_layers: tuple[Layer, ...] | None = None,
):
    """Return Component 3D trimesh Scene.

    Args:
        component: to extrude in 3D.
        layer_views: layer colors from Klayout Layer Properties file.
            Defaults to active PDK.layer_views.
        layer_stack: contains thickness and zmin for each layer.
            Defaults to active PDK.layer_stack.
        exclude_layers: layers to exclude.

    """
    from gdsfactory.pdk import get_active_pdk, get_layer_stack, get_layer_views

    try:
        from trimesh.creation import extrude_polygon
        from trimesh.scene import Scene
    except ImportError as e:
        print("you need to `pip install trimesh`")
        raise e

    layer_views = layer_views or get_layer_views()
    layer_stack = layer_stack or get_layer_stack()

    scene = Scene()
    layer_to_thickness = layer_stack.get_layer_to_thickness()
    layer_to_zmin = layer_stack.get_layer_to_zmin()
    exclude_layers = exclude_layers or ()
    # layers = layer_views.layer_map.values()

    component_with_booleans = layer_stack.get_component_with_derived_layers(component)
    polygons_per_layer = component_with_booleans.get_polygons_points()
    component_layers = polygons_per_layer.keys()
    has_polygons = False

    for layer, polygons in polygons_per_layer.items():
        if (
            layer not in exclude_layers
            and layer in layer_to_zmin
            and layer in layer_to_thickness
            and layer in component_layers
        ):
            height = layer_to_thickness[layer]
            zmin = layer_to_zmin[layer]
            layer_view = layer_views.get_from_tuple(layer)
            color_rgb = [
                c / 255 for c in layer_view.fill_color.as_rgb_tuple(alpha=False)
            ]
            # opacity = layer_view.get_alpha()

            if zmin is not None and layer_view.visible:
                has_polygons = True

                for polygon in [polygons]:
                    p = shapely.geometry.Polygon(polygon)
                    mesh = extrude_polygon(p, height=height)
                    mesh.apply_translation((0, 0, zmin))
                    mesh.visual.face_colors = (*color_rgb, 0.5)
                    scene.add_geometry(mesh)
    if not has_polygons:
        raise ValueError(
            f"{component.name!r} does not have polygons defined in the "
            f"layer_stack or layer_views for the active Pdk {get_active_pdk().name!r}"
        )
    return scene


if __name__ == "__main__":
    import gdsfactory as gf

    c = gf.components.mzi()
    # c = gf.Component()
    # c << gf.components.straight_heater_metal(length=40)
    # c << gf.c.rectangle(layer=(113, 0))
    # c = gf.components.grating_coupler_elliptical_trenches()
    # c = gf.components.taper_strip_to_ridge_trenches()

    c.show()
    s = c.to_3d()
    s.show()
