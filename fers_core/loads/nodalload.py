class NodalLoad:
    def __init__(self, node, load_case, magnitude: float, direction: tuple, load_type: str = "force"):
        """
        Initialize a nodal load.

        Args:
            node (Node): The node the load is applied to.
            load_case (LoadCase): The load case this load belongs to.
            magnitude (float): The magnitude of the load.
            direction (tuple): The direction of the load as a tuple (dx, dy, dz).
            load_type (str, optional): The type of the load ('force' or 'moment'). Defaults to 'force'.
        """
        self.node = node
        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.load_type = load_type

        # Automatically add this nodal load to the load case upon creation
        self.load_case.add_nodal_load(self)
