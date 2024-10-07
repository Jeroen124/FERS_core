class LineLoad:
    def __init__(
        self, member, load_case, magnitude: float, direction: tuple, start_pos: float = 0, end_pos: float = 1
    ):
        """
        Initialize a line load linked to a specific load case.

        Args:
            load_case: The LoadCase instance this line load is associated with.
            magnitude (float): The magnitude of the load per unit length.
            direction (tuple): The direction of the load as a tuple (dx, dy, dz).
            start_pos (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_pos (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        self.member = member
        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.start_pos = start_pos
        self.end_pos = end_pos

        # Automatically add this line load to the load case upon creation
        self.load_case.add_line_load(self)
