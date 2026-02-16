# FERS Visualization Architecture

This folder contains the modular visualization system for FERS.

## Overview

The visualization system uses a **decentralized architecture** where:

1. **Each element defines its own rendering** - Node, Member, etc. have `render()` methods
2. **Top-level renderers coordinate** - ModelRenderer and ResultRenderer orchestrate the visualization
3. **FERS provides access** - Model instances provide convenient access via `get_model_renderer()` and `get_result_renderer()`

This keeps the system modular and maintainable while centralizing only the coordination logic.

## Architecture

### Decentralized Rendering

Each structural element (Node, Member, etc.) defines its own rendering method:

```python
class Node:
    def render(self, annotation_size: float, theme: str) -> List[Tuple[pv.PolyData, str]]:
        """Returns list of (mesh, color) tuples"""
        pass

class Member:
    def render(self, theme: str) -> List[Tuple[pv.PolyData, str, int]]:
        """Returns list of (mesh, color, line_width) tuples"""
        pass
```

### Centralized Coordination

The renderer classes coordinate the overall visualization:

- **ModelRenderer**: Iterates through nodes and members, calling their render() methods
- **ResultRenderer**: Handles deformed shapes, diagrams, and contour plots

## Usage

### Basic Model Visualization

```python
from fers_core.fers.fers import FERS

# Create your model
model = FERS()
# ... add nodes, members, etc.

# Get the model renderer
renderer = model.get_model_renderer()

# Configure options
renderer.render_nodes = True
renderer.render_supports = True
renderer.labels = True

# Display
renderer.show()

# Or save screenshot
renderer.screenshot('my_model.png')
```

### Result Visualization

```python
# After running analysis
model.run_analysis()

# Get the result renderer
result_renderer = model.get_result_renderer()

# Show deformed shape
result_renderer.deformed_shape = True
result_renderer.deformed_scale = 50.0

# Show moment diagram
result_renderer.member_diagrams = 'My'
result_renderer.diagram_scale = 30.0

# Display
result_renderer.show()
```

### Using Existing Visualization Methods

FERS also maintains existing visualization methods for backward compatibility:

```python
# 3D model plot (existing method)
model.plot_model_3d(
    show_nodes=True,
    show_sections=True,
    show_supports=True
)

# 3D results (existing method)
model.show_results_3d(
    loadcombination=1,
    displacement=True,
    plot_bending_moment='M_y'
)
```

## Benefits

1. **Separation of Concerns**: Each class knows how to render itself
2. **Maintainability**: Rendering code lives with the class it represents
3. **Extensibility**: New element types automatically work if they have render() methods
4. **Flexibility**: Easy to customize rendering per element type

## Future Enhancements

- Support for load visualization
- Animated deformation sequences
- Interactive selection and highlighting
- Custom color schemes and themes
- Export to various formats (VTK, STL, etc.)
