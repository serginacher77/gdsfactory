import gdsfactory as gf

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.interpolate import CubicSpline

    c0 = gf.components.bend_circular(npoints=7)
    c0 = gf.components.bend_s(npoints=7)
    gdspath = c0.write_gds()
    c0.show()

    c = gf.import_gds(gdspath)
    points = c.get_polygons()[0]

    # Assume the points are ordered and the first half is the outer curve, the second half is the inner curve
    # This assumption might need to be adjusted based on your specific geometry
    mid_index = len(points) // 2
    outer_points = points[:mid_index]
    inner_points = points[mid_index:]
    inner_points = inner_points[::-1]

    # Define the interpolation function
    def interpolate_curve(points):
        t = np.arange(len(points))
        cs = CubicSpline(t, points)
        t_fine = np.linspace(t.min(), t.max(), 1000)
        return cs(t_fine)

    # Interpolate outer and inner curves
    outer_curve = interpolate_curve(outer_points)
    inner_curve = interpolate_curve(inner_points)

    # Calculate centerline as the average of inner and outer curves
    centerline = (outer_curve + inner_curve) / 2

    p = gf.Path(centerline)
    s, K = p.curvature()

    rmax = 200
    radius = 1 / K
    valid_indices = (radius > -rmax) & (radius < rmax)
    radius2 = radius[valid_indices]
    s2 = s[valid_indices]

    # Plotting
    plt.plot(s, K, ".-")
    plt.xlabel("Position along curve (arc length)")
    plt.ylabel("Curvature")

    plt.figure(figsize=(10, 5))
    plt.plot(s2, radius2, ".-")
    plt.xlabel("Position along curve (arc length)")
    plt.ylabel("Radius of curvature")

    plt.figure(figsize=(10, 5))
    plt.plot(outer_points[:, 0], outer_points[:, 1], "o", label="Outer Points")
    plt.plot(inner_points[:, 0], inner_points[:, 1], "o", label="Inner Points")
    plt.plot(outer_curve[:, 0], outer_curve[:, 1], "-", label="Outer Curve")
    plt.plot(inner_curve[:, 0], inner_curve[:, 1], "-", label="Inner Curve")
    plt.plot(centerline[:, 0], centerline[:, 1], "k--", label="Centerline")
    plt.legend()
    plt.title("Curve with Spline Interpolation for Inner and Outer Edges")
    plt.xlabel("X-coordinate")
    plt.ylabel("Y-coordinate")
    plt.grid(True)
    plt.show()
