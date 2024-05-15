import pupil_labs.neon_monitor as this_project


def test_package_metadata() -> None:
    assert hasattr(this_project, "__version__")
