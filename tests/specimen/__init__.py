"""The specimen strategy: a complete trivial strategy that only the conformance tests use.

The specimen is a test fixture, not a model for strategy code. It stays outside the closed production types
(``ToolName``, the selection union and the ``StrategyBehavior`` bounds) and reaches them only through
``tests.specimen.closed_types``. Strategy code never uses ``cast`` to cross the closed types: a real strategy is
added to them, and the generator's end-to-end test proves that without a cast.
"""
