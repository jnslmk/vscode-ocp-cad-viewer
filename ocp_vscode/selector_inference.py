"""Infer build123d selector expressions from shape geometry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import (
    GeomAbs_Circle,
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Line,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_Torus,
)
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS

if TYPE_CHECKING:
    from OCP.TopoDS import TopoDS_Shape


class ElementType(str, Enum):
    VERTEX = "vertex"
    EDGE = "edge"
    FACE = "face"


@dataclass
class GeometryInfo:
    """Geometric properties of a shape element."""

    element_type: ElementType
    index: int
    geometry_type: str
    center: tuple[float, float, float]
    normal: tuple[float, float, float] | None  # faces only
    area: float | None  # faces only
    length: float | None  # edges only
    radius: float | None  # circular edges/cylindrical faces


@dataclass
class SelectorSuggestion:
    """A suggested build123d selector expression."""

    expression: str
    confidence: str  # "high", "medium", "low"
    description: str


def get_shape_type(shape: TopoDS_Shape):
    """Get the shape type."""
    return shape.ShapeType()


def analyze_face(face) -> GeometryInfo:
    """Extract geometric properties from a face."""
    face = TopoDS.Face_s(face)
    adaptor = BRepAdaptor_Surface(face)
    surface_type = adaptor.GetType()

    # Get geometry type name
    geom_type_map = {
        GeomAbs_Plane: "Plane",
        GeomAbs_Cylinder: "Cylinder",
        GeomAbs_Cone: "Cone",
        GeomAbs_Sphere: "Sphere",
        GeomAbs_Torus: "Torus",
    }
    geometry_type = geom_type_map.get(surface_type, "BSpline")

    # Compute center and area
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    center_pnt = props.CentreOfMass()
    center = (round(center_pnt.X(), 4), round(center_pnt.Y(), 4), round(center_pnt.Z(), 4))
    area = round(props.Mass(), 4)

    # Get normal at center (for planar faces)
    normal = None
    if surface_type == GeomAbs_Plane:
        plane = adaptor.Plane()
        axis = plane.Axis()
        d = axis.Direction()
        normal = (round(d.X(), 4), round(d.Y(), 4), round(d.Z(), 4))

    # Get radius for cylindrical/spherical faces
    radius = None
    if surface_type == GeomAbs_Cylinder:
        radius = round(adaptor.Cylinder().Radius(), 4)
    elif surface_type == GeomAbs_Sphere:
        radius = round(adaptor.Sphere().Radius(), 4)

    return GeometryInfo(
        element_type=ElementType.FACE,
        index=-1,  # Set by caller
        geometry_type=geometry_type,
        center=center,
        normal=normal,
        area=area,
        length=None,
        radius=radius,
    )


def analyze_edge(edge) -> GeometryInfo:
    """Extract geometric properties from an edge."""
    edge = TopoDS.Edge_s(edge)
    adaptor = BRepAdaptor_Curve(edge)
    curve_type = adaptor.GetType()

    # Get geometry type name
    geom_type_map = {
        GeomAbs_Line: "Line",
        GeomAbs_Circle: "Circle",
    }
    geometry_type = geom_type_map.get(curve_type, "Curve")

    # Compute center and length
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    center_pnt = props.CentreOfMass()
    center = (round(center_pnt.X(), 4), round(center_pnt.Y(), 4), round(center_pnt.Z(), 4))
    length = round(props.Mass(), 4)

    # Get radius for circular edges
    radius = None
    if curve_type == GeomAbs_Circle:
        radius = round(adaptor.Circle().Radius(), 4)

    return GeometryInfo(
        element_type=ElementType.EDGE,
        index=-1,
        geometry_type=geometry_type,
        center=center,
        normal=None,
        area=None,
        length=length,
        radius=radius,
    )


def analyze_vertex(vertex) -> GeometryInfo:
    """Extract geometric properties from a vertex."""
    vertex = TopoDS.Vertex_s(vertex)
    pnt = BRep_Tool.Pnt_s(vertex)
    center = (round(pnt.X(), 4), round(pnt.Y(), 4), round(pnt.Z(), 4))

    return GeometryInfo(
        element_type=ElementType.VERTEX,
        index=-1,
        geometry_type="Point",
        center=center,
        normal=None,
        area=None,
        length=None,
        radius=None,
    )


def infer_selector(
    info: GeometryInfo,
    all_elements: list[GeometryInfo],
) -> SelectorSuggestion:
    """Infer a build123d selector expression for the given element.

    Args:
        info: The geometry info for the selected element
        all_elements: All elements of the same type in the shape (for uniqueness check)

    Returns:
        A selector suggestion with expression, confidence, and description
    """
    element_type = info.element_type
    collection = f"{element_type.value}s()"  # e.g., "faces()", "edges()", "vertices()"

    # Try position-based selectors (most reliable)
    for axis in ["Z", "Y", "X"]:
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
        sorted_elements = sorted(all_elements, key=lambda e: e.center[axis_idx])

        if info == sorted_elements[-1]:
            # This is the max element on this axis
            expr = f"{collection}.sort_by(Axis.{axis})[-1]"
            return SelectorSuggestion(
                expression=expr,
                confidence="high",
                description=f"Topmost along {axis} axis",
            )
        elif info == sorted_elements[0]:
            # This is the min element on this axis
            expr = f"{collection}.sort_by(Axis.{axis})[0]"
            return SelectorSuggestion(
                expression=expr,
                confidence="high",
                description=f"Bottommost along {axis} axis",
            )

    # Try geometry type filter
    same_geom = [e for e in all_elements if e.geometry_type == info.geometry_type]
    if len(same_geom) == 1:
        expr = f"{collection}.filter_by(GeomType.{info.geometry_type.upper()})"
        return SelectorSuggestion(
            expression=expr,
            confidence="high",
            description=f"Only {info.geometry_type} {element_type.value}",
        )

    # Try area/length extremes for faces/edges
    if element_type == ElementType.FACE and info.area is not None:
        sorted_by_area = sorted(all_elements, key=lambda e: e.area or 0)
        if info == sorted_by_area[-1]:
            expr = f"{collection}.sort_by(SortBy.AREA)[-1]"
            return SelectorSuggestion(
                expression=expr,
                confidence="high",
                description="Largest face by area",
            )
        elif info == sorted_by_area[0]:
            expr = f"{collection}.sort_by(SortBy.AREA)[0]"
            return SelectorSuggestion(
                expression=expr,
                confidence="high",
                description="Smallest face by area",
            )

    if element_type == ElementType.EDGE and info.length is not None:
        sorted_by_length = sorted(all_elements, key=lambda e: e.length or 0)
        if info == sorted_by_length[-1]:
            expr = f"{collection}.sort_by(SortBy.LENGTH)[-1]"
            return SelectorSuggestion(
                expression=expr,
                confidence="high",
                description="Longest edge",
            )
        elif info == sorted_by_length[0]:
            expr = f"{collection}.sort_by(SortBy.LENGTH)[0]"
            return SelectorSuggestion(
                expression=expr,
                confidence="high",
                description="Shortest edge",
            )

    # Fallback to index-based
    expr = f"{collection}[{info.index}]"
    return SelectorSuggestion(
        expression=expr,
        confidence="low",
        description="Index-based (may break if model changes)",
    )


def geometry_info_to_dict(info: GeometryInfo) -> dict:
    """Convert GeometryInfo to JSON-serializable dict."""
    return {
        "type": info.element_type.value,
        "index": info.index,
        "geometry": info.geometry_type,
        "center": list(info.center),
        "normal": list(info.normal) if info.normal else None,
        "area": info.area,
        "length": info.length,
        "radius": info.radius,
    }


def selector_to_dict(suggestion: SelectorSuggestion) -> dict:
    """Convert SelectorSuggestion to JSON-serializable dict."""
    return {
        "expression": suggestion.expression,
        "confidence": suggestion.confidence,
        "description": suggestion.description,
    }
