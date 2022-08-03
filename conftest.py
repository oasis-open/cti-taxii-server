
def pytest_addoption(parser):
    print("ASFESFASEFASEFASEFASE")
    parser.addoption("--backends", action="store", default="memory,mongo")

