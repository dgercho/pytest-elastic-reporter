import pytest


def test_passing():
    assert 1 + 1 == 2


def test_failing():
    assert 1 + 1 == 3, "The test passed by failing"


@pytest.mark.skip(reason="Not implemented")
def test_skipped():
    pass


@pytest.mark.parametrize("n", [2, 3, 4])
def test_parametrized(n):
    assert n > 1


@pytest.fixture
def working_fixture():
    return {"data": "testdata"}


def test_working_fixture(working_fixture):
    assert working_fixture["data"] == "testdata"


@pytest.fixture
def broken_fixture():
    alwaysTrue = True
    if alwaysTrue:
        raise RuntimeError("Fixture setup intentionally failed")
    yield


def test_broken_fixture(broken_fixture):
    assert broken_fixture is not None


@pytest.fixture
def broken_fixture2():
    yield 1
    raise RuntimeError("Fixture setup intentionally failed")


def test_broken_fixture2(broken_fixture2):
    assert broken_fixture2 == 1
