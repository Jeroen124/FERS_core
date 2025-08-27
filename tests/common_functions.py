from dataclasses import dataclass
import pytest
from typing import Tuple
from fers_core import Material, Section

# Centralized material and section builders -----------------------------------


def build_steel_s235() -> Material:
    return Material(
        name="Steel",
        e_mod=210_000_000_000.0,  # Pascals
        g_mod=80_769_000_000.0,  # Pascals
        density=7850.0,  # kg/m^3
        yield_stress=235_000_000.0,  # Pascals
    )


def build_ipe180(material: Material) -> Section:
    # Keep alignment with your examples: strong axis inertia = 10.63e-6
    # (Your example files put this in i_z; we keep those values to match FERS expectations.)
    return Section(
        name="IPE 180 Beam Section",
        material=material,
        i_y=0.819e-6,  # m^4  (weak)
        i_z=10.63e-6,  # m^4  (strong)
        j=0.027e-6,  # m^4
        area=0.00196,  # m^2
    )


# Tolerances -------------------------------------------------------------------


@dataclass
class ComparisonTolerances:
    absolute_displacement_in_meter: float = 1e-6
    absolute_moment_in_newton_meter: float = 1e-3
    absolute_force_in_newton: float = 1e-6
    relative: float = 1e-5


TOL = ComparisonTolerances()


def assert_close(
    actual: float,
    expected: float,
    *,
    abs_tol: float,
    rel_tol: float = TOL.relative,
    label: str | None = None,
    **context,
) -> None:
    """
    Assert that 'actual' is close to 'expected' with the given tolerances.
    On failure, print a detailed message including the inputs and tolerances.

    You can pass an optional 'label' and any number of keyword args (context)
    that will be printed if the assertion fails.
    """
    try:
        assert actual == pytest.approx(expected, rel=rel_tol, abs=abs_tol)
    except AssertionError:
        absolute_difference = abs(actual - expected)
        # Avoid division by zero in relative difference
        denom = abs(expected) if expected != 0 else 1.0
        relative_difference = absolute_difference / denom

        lines = []
        if label:
            lines.append(f"{label}")
        lines.append(f"actual = {actual!r}")
        lines.append(f"expected = {expected!r}")
        lines.append(f"absolute_difference = {absolute_difference!r}")
        lines.append(f"relative_difference = {relative_difference!r}")
        lines.append(f"absolute_tolerance = {abs_tol!r}")
        lines.append(f"relative_tolerance = {rel_tol!r}")

        # Any extra named inputs you pass to this function will be printed here.
        for key, value in context.items():
            lines.append(f"{key} = {value!r}")

        pytest.fail("\n".join(lines))


# Beam-theory helpers (closed-form) -------------------------------------------


def cantilever_end_point_load_deflection_at_free_end(
    force_in_newton: float,
    beam_length_in_meter: float,
    modulus_of_elasticity_in_pascal: float,
    second_moment_of_area_in_m_to_power_4: float,
) -> float:
    return -(force_in_newton * beam_length_in_meter**3) / (
        3.0 * modulus_of_elasticity_in_pascal * second_moment_of_area_in_m_to_power_4
    )


def cantilever_end_point_load_fixed_end_moment_magnitude(
    force_in_newton: float, beam_length_in_meter: float
) -> float:
    return force_in_newton * beam_length_in_meter


def cantilever_point_load_deflection_at_position_a(
    force_in_newton: float,
    position_a_in_meter: float,
    modulus_of_elasticity_in_pascal: float,
    second_moment_of_area_in_m_to_power_4: float,
) -> float:
    return -(force_in_newton * position_a_in_meter**3) / (
        3.0 * modulus_of_elasticity_in_pascal * second_moment_of_area_in_m_to_power_4
    )


def cantilever_point_load_deflection_at_free_end_from_a(
    force_in_newton: float,
    beam_length_in_meter: float,
    position_a_in_meter: float,
    modulus_of_elasticity_in_pascal: float,
    second_moment_of_area_in_m_to_power_4: float,
) -> float:
    return (
        -(force_in_newton * position_a_in_meter**2)
        * (3.0 * beam_length_in_meter - position_a_in_meter)
        / (6.0 * modulus_of_elasticity_in_pascal * second_moment_of_area_in_m_to_power_4)
    )


def cantilever_uniform_load_deflection_at_free_end(
    load_intensity_in_newton_per_meter: float,
    beam_length_in_meter: float,
    modulus_of_elasticity_in_pascal: float,
    second_moment_of_area_in_m_to_power_4: float,
) -> float:
    return -(load_intensity_in_newton_per_meter * beam_length_in_meter**4) / (
        8.0 * modulus_of_elasticity_in_pascal * second_moment_of_area_in_m_to_power_4
    )


def cantilever_uniform_load_fixed_end_moment(
    load_intensity_in_newton_per_meter: float, beam_length_in_meter: float
) -> float:
    return load_intensity_in_newton_per_meter * beam_length_in_meter**2 / 2.0


def cantilever_full_triangular_fixed_end_moment(
    load_intensity_in_newton_per_meter: float, beam_length_in_meter: float
) -> float:
    # Triangular with zero at fixed end, peak at free end (matches your example 005)
    return load_intensity_in_newton_per_meter * beam_length_in_meter**2 / 6.0


def cantilever_full_inverse_triangular_fixed_end_moment(
    load_intensity_in_newton_per_meter: float, beam_length_in_meter: float
) -> float:
    # Inverse triangular with peak at fixed end, zero at free end (matches your example 005)
    return load_intensity_in_newton_per_meter * beam_length_in_meter**2 / 3.0


def cantilever_full_triangular_deflection_at_free_end(
    load_intensity_in_newton_per_meter: float,
    beam_length_in_meter: float,
    modulus_of_elasticity_in_pascal: float,
    second_moment_of_area_in_m_to_power_4: float,
) -> float:
    return -(load_intensity_in_newton_per_meter * beam_length_in_meter**4) / (
        30.0 * modulus_of_elasticity_in_pascal * second_moment_of_area_in_m_to_power_4
    )


def cantilever_partial_uniform_resultant_and_fixed_moment(
    load_intensity_in_newton_per_meter: float,
    beam_length_in_meter: float,
    start_fraction: float,
    end_fraction: float,
) -> Tuple[float, float]:
    start_position_in_meter = start_fraction * beam_length_in_meter
    end_position_in_meter = end_fraction * beam_length_in_meter
    resultant_force_in_newton = load_intensity_in_newton_per_meter * (
        end_position_in_meter - start_position_in_meter
    )
    centroid_from_fixed_in_meter = 0.5 * (start_position_in_meter + end_position_in_meter)
    fixed_end_moment_in_newton_meter = resultant_force_in_newton * centroid_from_fixed_in_meter
    return resultant_force_in_newton, fixed_end_moment_in_newton_meter


def cantilever_partial_triangular_resultant_and_fixed_moment(
    load_intensity_in_newton_per_meter: float,
    beam_length_in_meter: float,
    start_fraction: float,
    end_fraction: float,
    inverse: bool,
) -> Tuple[float, float]:
    # Matches your 006 formulas exactly.
    span_fraction = end_fraction - start_fraction
    resultant_force_in_newton = (
        load_intensity_in_newton_per_meter * 0.5 * beam_length_in_meter * span_fraction
    )
    if not inverse:
        # centroid one third from the "heavier" end => at (start + end) / 3 from fixed when peak is at end
        centroid_from_fixed_in_meter = (start_fraction + end_fraction) * beam_length_in_meter * (1.0 / 3.0)
    else:
        # inverse triangular: peak nearer to start side (use your example’s centroid expression)
        centroid_from_fixed_in_meter = (start_fraction + (2.0 / 3.0) * span_fraction) * beam_length_in_meter
    fixed_end_moment_in_newton_meter = resultant_force_in_newton * centroid_from_fixed_in_meter
    return resultant_force_in_newton, fixed_end_moment_in_newton_meter


# Simply supported beam helpers ------------------------------------------------


def simply_supported_center_point_load_deflection_at_midspan(
    force_in_newton: float,
    beam_length_in_meter: float,
    modulus_of_elasticity_in_pascal: float,
    second_moment_of_area_in_m_to_power_4: float,
) -> float:
    return -(force_in_newton * beam_length_in_meter**3) / (
        48.0 * modulus_of_elasticity_in_pascal * second_moment_of_area_in_m_to_power_4
    )


def simply_supported_center_point_load_max_moment(
    force_in_newton: float, beam_length_in_meter: float
) -> float:
    return (force_in_newton * beam_length_in_meter) / 4.0


def simply_supported_reactions_for_point_load_at_x(
    force_in_newton: float, beam_length_in_meter: float, position_from_left_in_meter: float
) -> Tuple[float, float]:
    reaction_at_left_in_newton = (
        force_in_newton * (beam_length_in_meter - position_from_left_in_meter) / beam_length_in_meter
    )
    reaction_at_right_in_newton = force_in_newton * position_from_left_in_meter / beam_length_in_meter
    return reaction_at_left_in_newton, reaction_at_right_in_newton


def simply_supported_symmetric_double_load_mid_moment(
    force_per_point_in_newton: float, distance_from_support_in_meter: float
) -> float:
    # Matches your 013 example: M_mid = F * a
    return force_per_point_in_newton * distance_from_support_in_meter
