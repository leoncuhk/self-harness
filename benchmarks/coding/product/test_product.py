from calculator import add


def test_positive_numbers() -> None:
    assert add(2, 3) == 5


def test_negative_numbers() -> None:
    assert add(-2, 3) == 1
