"Quadrature representation class for UFL"

# Copyright (C) 2009-2014 Kristian B. Oelgaard
#
# This file is part of FFC.
#
# FFC is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FFC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with FFC. If not, see <http://www.gnu.org/licenses/>.
#
# Modified by Anders Logg, 2009.
# Modified by Martin Alnaes, 2013-2014

import numpy

# UFL modules
import ufl
from ufl.classes import Grad, CellAvg, FacetAvg
from ufl.algorithms import extract_unique_elements, extract_type, extract_elements

# FFC modules
from ffc.log import ffc_assert, info, error
from ffc.fiatinterface import create_element
from ffc.fiatinterface import map_facet_points, reference_cell_vertices
from ffc.fiatinterface import cell_to_num_entities
from ffc.quadrature_schemes import create_quadrature

def _create_quadrature_points_and_weights(integral_type, cell, degree, rule):
    if integral_type == "cell":
        (points, weights) = create_quadrature(cell, degree, rule)
    elif integral_type == "exterior_facet" or integral_type == "interior_facet":
        (points, weights) = create_quadrature(cell.facet_cellname(), degree, rule)
    elif integral_type in ("exterior_facet_top", "exterior_facet_bottom", "interior_facet_horiz"):
        (points, weights) = create_quadrature(cell.facet_horiz, degree[0], rule)
    elif integral_type in ("exterior_facet_vert", "interior_facet_vert"):
        if cell.topological_dimension() == 2:
            # extruded interval, so the vertical facet is a line, not an OP cell
            (points, weights) = create_quadrature(cell.facet_vert, degree[1], rule)
        else:
            (points, weights) = create_quadrature(cell.facet_vert, degree, rule)
    elif integral_type == "point":
        (points, weights) = ([()], numpy.array([1.0,])) # TODO: Will be fixed
    else:
        error("Unknown integral type: " + str(integral_type))
    return (points, weights)

def _find_element_derivatives(expr, elements, element_replace_map):
    "Find the highest derivatives of given elements in expression."
    # TODO: This is most likely not the best way to get the highest
    #       derivative of an element, but it works!

    # Initialise dictionary of elements and the number of derivatives.
    # (Note that elements are already mapped through the element_replace_map)
    num_derivatives = dict((e, 0) for e in elements)

    # Extract the derivatives from the integral.
    derivatives = set(extract_type(expr, Grad))

    # Loop derivatives and extract multiple derivatives.
    for d in list(derivatives):
        # After UFL has evaluated derivatives, only one element
        # can be found inside any single Grad expression
        elem, = extract_elements(d.operands()[0])
        elem = element_replace_map[elem]
        # Set the number of derivatives to the highest value encountered so far.
        num_derivatives[elem] = max(num_derivatives[elem], len(extract_type(d, Grad)))
    return num_derivatives

def domain_to_entity_dim(integral_type, cell):
    tdim = cell.topological_dimension()
    if integral_type == "cell":
        entity_dim = tdim
    elif (integral_type in ("exterior_facet", "interior_facet", "exterior_facet_top", "exterior_facet_bottom", "exterior_facet_vert", "interior_facet_horiz", "interior_facet_vert")):
        entity_dim = tdim - 1
    elif integral_type == "point":
        entity_dim = 0
    else:
        error("Unknown integral_type: %s" % integral_type)
    return entity_dim

def _map_entity_points(cell, points, entity_dim, entity, integral_type):
    # Not sure if this is useful anywhere else than in _tabulate_psi_table!
    tdim = cell.topological_dimension()
    if entity_dim == tdim:
        return points
    elif entity_dim == tdim-1:
        if integral_type in ("exterior_facet_top", "exterior_facet_bottom", "interior_facet_horiz"):
            return map_facet_points(points, entity, "horiz_facet")
        elif integral_type in ("exterior_facet_vert", "interior_facet_vert"):
            return map_facet_points(points, entity, "vert_facet")
        else:
            return map_facet_points(points, entity, "facet")
    elif entity_dim == 0:
        return (reference_cell_vertices(cell.cellname())[entity],)

def _tabulate_psi_table(integral_type, cell, element, deriv_order, points):
    "Tabulate psi table for different integral types."
    # MSA: I attempted to generalize this function, could this way of
    # handling domain types generically extend to other parts of the code?
    entity_dim = domain_to_entity_dim(integral_type, cell)
    if integral_type in ("exterior_facet_top", "exterior_facet_bottom", "interior_facet_horiz"):
        num_entities = 2  # top and bottom
    elif integral_type in ("exterior_facet_vert", "interior_facet_vert"):
        num_entities = cell_to_num_entities(cell._A)[-2]  # number of "base cell" facets
    else:
        num_entities = cell_to_num_entities(cell)[entity_dim]
    psi_table = {}
    for entity in range(num_entities):
        entity_points = _map_entity_points(cell, points, entity_dim, entity, integral_type)
        # TODO: Use 0 as key for cell and we may be able to generalize other places:
        key = None if integral_type == "cell" else entity
        psi_table[key] = element.tabulate(deriv_order, entity_points)
    return psi_table

def _tabulate_entities(integral_type, cell):
    "Tabulate psi table for different integral types."
    # MSA: I attempted to generalize this function, could this way of
    # handling domain types generically extend to other parts of the code?
    entity_dim = domain_to_entity_dim(integral_type, cell)
    num_entities = cellname_to_num_entities[cell.cellname()][entity_dim]
    entities = set()
    for entity in range(num_entities):
        # TODO: Use 0 as key for cell and we may be able to generalize other places:
        key = None if integral_type == "cell" else entity
        entities.add(key)
    return entities

def insert_nested_dict(root, keys, value):
    for k in keys[:-1]:
        d = root.get(k)
        if d is None:
            d = {}
            root[k] = d
        root = d
    root[keys[-1]] = value


# MSA: This function is in serious need for some refactoring and splitting up.
#      Or perhaps I should just add a new implementation for uflacs,
#      but I'd rather not have two versions to maintain.
def tabulate_basis(sorted_integrals, form_data, itg_data):
    "Tabulate the basisfunctions and derivatives."

    # MER: Note to newbies: this code assumes that each integral in
    # the dictionary of sorted_integrals that enters here, has a
    # unique number of quadrature points ...

    # Initialise return values.
    quadrature_rules = {}
    psi_tables = {}
    integrals = {}
    avg_elements = { "cell": [], "facet": [] }

    integral_type = itg_data.integral_type
    cell = itg_data.domain.cell()

    # Loop the quadrature points and tabulate the basis values.
    rules = sorted(sorted_integrals.keys())
    for degree, scheme in rules:

        # --------- Creating quadrature rule
        # Make quadrature rule and get points and weights.
        (points, weights) = _create_quadrature_points_and_weights(integral_type, cell, degree, scheme)
        # The TOTAL number of weights/points
        len_weights = len(weights)
        # Add points and rules to dictionary
        ffc_assert(len_weights not in quadrature_rules,
                   "This number of points is already present in the weight table: " + repr(quadrature_rules))
        quadrature_rules[len_weights] = (weights, points)


        # --------- Store integral

        # Add the integral with the number of points as a key to the return integrals.
        integral = sorted_integrals[(degree, scheme)]
        ffc_assert(len_weights not in integrals, \
                   "This number of points is already present in the integrals: " + repr(integrals))
        integrals[len_weights] = integral


        # --------- Analyse UFL elements in integral

        # Get all unique elements in integral.
        ufl_elements = [form_data.element_replace_map[e]
                        for e in extract_unique_elements(integral)]

        # Insert elements for x and J
        domain = integral.domain() # FIXME: For all domains to be sure? Better to rewrite though.
        x = domain.coordinates()
        if x is None:
            x_element = ufl.VectorElement("Lagrange", domain, 1)
        else:
            x_element = x.element()
        if x_element not in ufl_elements:
            ufl_elements.append(x_element)

        # Find all CellAvg and FacetAvg in integrals and extract elements
        for avg, AvgType in (("cell", CellAvg), ("facet", FacetAvg)):
            expressions = extract_type(integral, AvgType)
            avg_elements[avg] = [form_data.element_replace_map[e]
                                 for expr in expressions
                                 for e in extract_unique_elements(expr)]

        # Find the highest number of derivatives needed for each element
        num_derivatives = _find_element_derivatives(integral.integrand(), ufl_elements,
                                                    form_data.element_replace_map)
        # Need at least 1 for the Jacobian
        num_derivatives[x_element] = max(num_derivatives.get(x_element,0), 1)


        # --------- Evaluate FIAT elements in quadrature points and store in tables

        # Add the number of points to the psi tables dictionary.
        ffc_assert(len_weights not in psi_tables, \
                   "This number of points is already present in the psi table: " + repr(psi_tables))
        psi_tables[len_weights] = {}

        # Loop FIAT elements and tabulate basis as usual.
        for ufl_element in ufl_elements:
            fiat_element = create_element(ufl_element)

            # Tabulate table of basis functions and derivatives in points
            psi_table = _tabulate_psi_table(integral_type, cell, fiat_element,
                                        num_derivatives[ufl_element], points)

            # Insert table into dictionary based on UFL elements. (None=not averaged)
            psi_tables[len_weights][ufl_element] = { None: psi_table }


    # Loop over elements found in CellAvg and tabulate basis averages
    len_weights = 1
    for avg in ("cell", "facet"):
        # Doesn't matter if it's exterior or interior
        if avg == "cell":
            avg_integral_type = "cell"
        elif avg == "facet":
            avg_integral_type = "exterior_facet"

        for element in avg_elements[avg]:
            fiat_element = create_element(element)

            # Make quadrature rule and get points and weights.
            (points, weights) = _create_quadrature_points_and_weights(avg_integral_type, cell, element.degree(), "default")
            wsum = sum(weights)

            # Tabulate table of basis functions and derivatives in points
            entity_psi_tables = _tabulate_psi_table(avg_integral_type, cell, fiat_element, 0, points)
            rank = len(element.value_shape())

            # Hack, duplicating table with per-cell values for each facet in the case of cell_avg(f) in a facet integral
            actual_entities = _tabulate_entities(integral_type, cell)
            if len(actual_entities) > len(entity_psi_tables):
                assert len(entity_psi_tables) == 1
                assert avg_integral_type == "cell"
                assert "facet" in integral_type
                v, = entity_psi_tables.values()
                entity_psi_tables = dict((e, v) for e in actual_entities)

            for entity, deriv_table in entity_psi_tables.items():
                deriv, = list(deriv_table.keys()) # Not expecting derivatives of averages
                psi_table = deriv_table[deriv]

                if rank:
                    # Compute numeric integral
                    num_dofs, num_components, num_points = psi_table.shape
                    ffc_assert(num_points == len(weights), "Weights and table shape does not match.")
                    avg_psi_table = numpy.asarray([[[numpy.dot(psi_table[j,k,:], weights) / wsum]
                                                   for k in range(num_components)]
                                                   for j in range(num_dofs)])
                else:
                    # Compute numeric integral
                    num_dofs, num_points = psi_table.shape
                    ffc_assert(num_points == len(weights), "Weights and table shape does not match.")
                    avg_psi_table = numpy.asarray([[numpy.dot(psi_table[j,:], weights) / wsum] for j in range(num_dofs)])

                # Insert table into dictionary based on UFL elements.
                insert_nested_dict(psi_tables, (len_weights, element, avg, entity, deriv), avg_psi_table)

    return (integrals, psi_tables, quadrature_rules)
