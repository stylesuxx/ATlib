from .Operator import Operator


def is_valid_operator(operator: str) -> bool:
    """ Check for validity of operator string. """
    invalid_operators = ["0,1,2,3,4", "0,1,2"]

    return operator not in invalid_operators


def sanitize_operator(operator: str) -> Operator:
    """ Convert operator string to object """
    tuple = operator.split(",")
    access_technologies = None
    if len(tuple) >= 5:
        access_technologies = int(tuple[4].replace("\"", ""))

    operator = Operator(
        int(tuple[0].replace("\"", "")),
        tuple[1].replace("\"", ""),
        tuple[2].replace("\"", ""),
        int(tuple[3].replace("\"", "")),
        access_technologies,
    )

    return operator
