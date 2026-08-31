Timeline requests now commit state changes before rendering in a read-only transaction; experiments that write from ``render()`` or templates must move those changes to ``pre_render()``.
