// This file was automatically generated by FFC, the FEniCS Form Compiler.
// Licensed under the GNU GPL Version 2.

#ifndef __MASSMATRIX_H
#define __MASSMATRIX_H

#include <dolfin/NewFiniteElement.h>
#include <dolfin/LinearForm.h>
#include <dolfin/BilinearForm.h>

namespace dolfin { namespace MassMatrix {

/// This is the finite element for which the form is generated,
/// providing the information neccessary to do assembly.

class FiniteElement : public dolfin::NewFiniteElement
{
public:

  FiniteElement() : dolfin::NewFiniteElement(), tensordims(0)
  {
    // Do nothing
  }

  ~FiniteElement()
  {
    if ( tensordims ) delete [] tensordims;
  }

  inline unsigned int spacedim() const
  {
    return 3;
  }

  inline unsigned int shapedim() const
  {
    return 2;
  }

  inline unsigned int tensordim(unsigned int i) const
  {
    dolfin_error("Element is scalar.");
    return 0;
  }

  inline unsigned int rank() const
  {
    return 0;
  }

  // FIXME: Only works for nodal basis
  inline unsigned int dof(unsigned int i, const Cell& cell, const Mesh& mesh) const
  {
    return cell.nodeID(i);
  }

  // FIXME: Only works for nodal basis
  inline const Point coord(unsigned int i, const Cell& cell, const Mesh& mesh) const
  {
    return cell.node(i).coord();
  }

private:

  unsigned int* tensordims;

};

/// This class contains the form to be evaluated, including
/// contributions from the interior and boundary of the domain.

class BilinearForm : public dolfin::BilinearForm
{
public:

  BilinearForm() : dolfin::BilinearForm()
  {
  }

  bool interior(real* block) const
  {
    // Compute geometry tensors
    real G0_ = det;

    // Compute element tensor
    block[0] = 0.0833333333333*G0_;
    block[1] = 0.0416666666667*G0_;
    block[2] = 0.0416666666667*G0_;
    block[3] = 0.0416666666667*G0_;
    block[4] = 0.0833333333333*G0_;
    block[5] = 0.0416666666667*G0_;
    block[6] = 0.0416666666667*G0_;
    block[7] = 0.0416666666667*G0_;
    block[8] = 0.0833333333333*G0_;

    return true;
  }

};

} }

#endif
