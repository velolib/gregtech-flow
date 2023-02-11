"""Exceptions for GT: Flow."""


class GTFlowError(Exception):
    """Base exception for GT: Flow."""
    pass


class SolverError(GTFlowError):
    """Error while running the GT: Flow equations solver."""
    pass


class OverclockError(GTFlowError):
    """Error while overclocking."""
    pass
