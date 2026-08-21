def test_a2a_sdk_not_shadowed():
    import a2a.types

    assert a2a.types.__name__ == "a2a.types"
