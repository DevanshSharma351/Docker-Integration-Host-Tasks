import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--integration',
        action='store_true',
        default=False,
        help='Run integration tests against real Docker daemon'
    )


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'integration: mark test as requiring a real Docker daemon'
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--integration'):
        skip = pytest.mark.skip(reason='Pass --integration to run')
        for item in items:
            if 'integration' in item.keywords:
                item.add_marker(skip)