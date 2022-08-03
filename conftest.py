
def pytest_addoption(parser):
    parser.addoption("--backends", action="store", default="memory,mongo")

