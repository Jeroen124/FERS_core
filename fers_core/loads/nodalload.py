class NodalLoad:
    _nodal_load_counter = 1

    def __init__(self, node, load_case, magnitude: float, direction: tuple, load_type: str = "force"):
        """
        Initialize a nodal load.

        Args:
            node (Node): The node the load is applied to.
            load_case (LoadCase): The load case this load belongs to.
            magnitude (float): The magnitude of the load.
            direction (tuple): The direction of the load in global reference frame as a tuple (X, Y, Z).
            load_type (str, optional): The type of the load ('force' or 'moment'). Defaults to 'force'.
        """
        self.id = NodalLoad._nodal_load_counter
        NodalLoad._nodal_load_counter += 1
        self.node = node
        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.load_type = load_type

        # Automatically add this nodal load to the load case upon creation
        self.load_case.add_nodal_load(self)

    @classmethod
    def reset_counter(cls):
        cls._nodal_load_counter = 1

    def to_dict(self):
        return {
            "id": self.id,
            "node": self.node.id,
            "load_case": self.load_case.id,
            "magnitude": self.magnitude,
            "direction": self.direction,
            "load_type": self.load_type,
        }
