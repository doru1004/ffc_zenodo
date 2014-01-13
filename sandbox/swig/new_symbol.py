"This file contains functions to optimise the code generated for quadrature representation."

# Copyright (C) 2009-2010 Kristian B. Oelgaard
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
# First added:  2009-07-12
# Last changed: 2010-01-21

# FFC common modules
from ffc.common.log import debug, error

#import psyco
#psyco.full()

# TODO: Use proper errors, not just RuntimeError.
# TODO: Change all if value == 0.0 to something more safe.

# Some basic variables.
BASIS = 0
IP  = 1
GEO = 2
CONST = 3
type_to_string = {BASIS:"BASIS", IP:"IP",GEO:"GEO", CONST:"CONST"}
format = None

# Functions and dictionaries for cache implementation.
# Increases speed and should also reduce memory consumption.
_float_cache = {}
def create_float(val):
    if val in _float_cache:
#        print "found %f in cache" %val
        return _float_cache[val]
    float_val = FloatValue(val)
    _float_cache[val] = float_val
    return float_val

_symbol_cache = {}
def create_symbol(variable, symbol_type, base_expr=None, base_op=0):
    key = (variable, symbol_type, base_expr, base_op)
    if key in _symbol_cache:
#        print "found %s in cache" %variable
        return _symbol_cache[key]
    symbol = Symbol(variable, symbol_type, base_expr, base_op)
    _symbol_cache[key] = symbol
    return symbol

_product_cache = {}
def create_product(variables):
    # NOTE: If I switch on the sorted line, it might be possible to find more
    # variables in the cache, but it adds some overhead so I don't think it
    # pays off. The member variables are also sorted in the classes
    # (Product and Sum) so the list 'variables' is probably already sorted.
#    key = tuple(sorted(variables))
    key = tuple(variables)
    if key in _product_cache:
#        print "found %s in cache" %str(key)
        return _product_cache[key]
    product = Product(key)
    _product_cache[key] = product
    return product

_sum_cache = {}
def create_sum(variables):
    # NOTE: If I switch on the sorted line, it might be possible to find more
    # variables in the cache, but it adds some overhead so I don't think it
    # pays off. The member variables are also sorted in the classes
    # (Product and Sum) so the list 'variables' is probably already sorted.
#    key = tuple(sorted(variables))
    key = tuple(variables)
    if key in _sum_cache:
#        print "found %s in cache" %str(key)
        return _sum_cache[key]
    s = Sum(key)
    _sum_cache[key] = s
    return s

_fraction_cache = {}
def create_fraction(num, denom):
    key = (num, denom)
    if key in _fraction_cache:
#        print "found %s in cache" %str(key)
        return _fraction_cache[key]
    fraction = Fraction(num, denom)
    _fraction_cache[key] = fraction
    return fraction

# Function to set global format to avoid passing around the dictionary 'format'.
def set_format(_format):
    global format
    format = _format
    set_format_float(format)
    set_format_prod(format)
    set_format_sum(format)
    set_format_frac(format)
    global format_comment
    format_comment = format["comment"]

def get_format():
    return format

# NOTE: We use commented print for debug, since debug will make the code run slower.
def generate_aux_constants(constant_decl, name, var_type, print_ops=False):
    "A helper tool to generate code for constant declarations."
    code = []
    append = code.append
    ops = 0
    for s in sorted([(v, k) for k, v in constant_decl.iteritems()]):
        c = s[1]
#        debug("c orig: " + str(c))
#        prit "c orig: " + str(c)
        c = c.expand().reduce_ops()
#        debug("c opt:  " + str(c))
#        print "c opt:  " + str(c)
        if print_ops:
            op = c.ops()
            ops += op
            append(format_comment("Number of operations: %d" %op))
            append((var_type + name + str(s[0]), str(c)))
            append("")
        else:
            ops += c.ops()
            append((var_type + name + str(s[0]), str(c)))

    return (ops, code)

def optimise_code(expr, ip_consts, geo_consts, trans_set):
    """Optimise a given expression with respect to, basis functions,
    integration points variables and geometric constants.
    The function will update the dictionaries ip_const and geo_consts with new
    declarations and update the trans_set (used transformations)."""

    format_G  = format["geometry tensor"]
    format_ip = format["integration points"]
    trans_set_update = trans_set.update

    # Return constant symbol if value is zero.
    if expr.val == 0.0:
        return create_float(0)

    # Reduce expression with respect to basis function variable.
#    debug("\n\nexpr before exp: " + repr(expr))
#    print "\n\nexpr before exp: " + repr(expr)
    basis_expressions = expr.expand().reduce_vartype(BASIS)

    # If we had a product instance we'll get a tuple back so embed in list.
    if not isinstance(basis_expressions, list):
        basis_expressions = [basis_expressions]

    basis_vals = []
    # Process each instance of basis functions.
    for basis, ip_expr in basis_expressions:
        # Get the basis and the ip expression.
#        debug("\nbasis\n" + str(basis))
#        debug("ip_epxr\n" + str(ip_expr))
#        print "\nbasis\n" + str(basis)
#        print "ip_epxr\n" + str(ip_expr)

        # If we have no basis (like functionals) create a const.
        if not basis:
            basis = create_float(1)
        # NOTE: Useful for debugging to check that terms where properly reduced.
#        if Product([basis, ip_expr]).expand() != expr.expand():
#            prod = Product([basis, ip_expr]).expand()
#            print "prod == sum: ", isinstance(prod, Sum)
#            print "expr == sum: ", isinstance(expr, Sum)

#            print "prod.vrs: ", prod.vrs
#            print "expr.vrs: ", expr.vrs
#            print "expr.vrs = prod.vrs: ", expr.vrs == prod.vrs

#            print "equal: ", prod == expr

#            print "\nprod:    ", prod
#            print "\nexpr:    ", expr
#            print "\nbasis:   ", basis
#            print "\nip_expr: ", ip_expr
#            error("Not equal")

        # If the ip expression doesn't contain any operations skip remainder.
        if not ip_expr:
            basis_vals.append(basis)
            continue
        if not ip_expr.ops() > 0:
            basis_vals.append(create_product([basis, ip_expr]))
            continue

        # Reduce the ip expressions with respect to IP variables.
        ip_expressions = ip_expr.expand().reduce_vartype(IP)

        # If we had a product instance we'll get a tuple back so embed in list.
        if not isinstance(ip_expressions, list):
            ip_expressions = [ip_expressions]

        ip_vals = []
        # Loop ip expressions.
        for ip in ip_expressions:
            ip_dec, geo = ip
#            debug("\nip_dec: " + str(ip_dec))
#            debug("\ngeo: " + str(geo))
#            print "\nip_dec: " + str(ip_dec)
#            print "\ngeo: " + str(geo)
            # Update transformation set with those values that might be embedded in IP terms.
            if ip_dec:
                trans_set_update(map(lambda x: str(x), ip_dec.get_unique_vars(GEO)))

            # Append and continue if we did not have any geo values.
            if not geo:
                ip_vals.append(ip_dec)
                continue

            # Update the transformation set with the variables in the geo term.
            trans_set_update(map(lambda x: str(x), geo.get_unique_vars(GEO)))

            # Only declare auxiliary geo terms if we can save operations.
            if geo.ops() > 0:
#                debug("geo: " + str(geo))
#                print "geo: " + str(geo)
                # If the geo term is not in the dictionary append it.
                if not geo_consts.has_key(geo):
                    geo_consts[geo] = len(geo_consts)

                # Substitute geometry expression.
                geo = create_symbol(format_G + str(geo_consts[geo]), GEO)

            # If we did not have any ip_declarations use geo, else create a
            # product and append to the list of ip_values.
            if not ip_dec:
                ip_dec = geo
            else:
                ip_dec = create_product([ip_dec, geo])
            ip_vals.append(ip_dec)

        # Create sum of ip expressions to multiply by basis.
        if len(ip_vals) > 1:
            ip_expr = create_sum(ip_vals)
        elif ip_vals:
            ip_expr = ip_vals.pop()

        # If we can save operations by declaring it as a constant do so, if it
        # is not in IP dictionary, add it and use new name.
        if ip_expr.ops() > 0:
            if not ip_expr in ip_consts:
                ip_consts[ip_expr] = len(ip_consts)

            # Substitute ip expression.
            ip_expr = create_symbol(format_G + format_ip + str(ip_consts[ip_expr]), IP)

        # Multiply by basis and append to basis vals.
        basis_vals.append(create_product([basis, ip_expr]).expand())

    # Return sum of basis values.
    return create_sum(basis_vals)

from floatvalue_obj import FloatValue, set_format as set_format_float
from symbol_obj     import Symbol
from product_obj    import Product, set_format as set_format_prod
from sum_obj        import Sum, group_fractions, set_format as set_format_sum
from fraction_obj   import Fraction, set_format as set_format_frac
