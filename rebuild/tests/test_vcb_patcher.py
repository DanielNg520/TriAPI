from scripts.vcb_patcher import apply_and_verify


def test_apply_and_verify_success():
    original = "def add(a, b):\n    return a + b\n"
    response_text = (
        "<<<<<<< SEARCH\n"
        "    return a + b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    new_content, error_kind, error_message = apply_and_verify(original, response_text)
    assert new_content == "def add(a, b):\n    return a * b\n"
    assert error_kind is None
    assert error_message == ""


def test_apply_and_verify_apply_failure():
    original = "def add(a, b):\n    return a + b\n"
    response_text = (
        "<<<<<<< SEARCH\n"
        "    return a - b\n"
        "=======\n"
        "    return a * b\n"
        ">>>>>>> REPLACE"
    )
    new_content, error_kind, error_message = apply_and_verify(original, response_text)
    assert new_content is None
    assert error_kind == "apply"
    assert bool(error_message)


def test_apply_and_verify_syntax_failure():
    original = "def add(a, b):\n    return a + b\n"
    response_text = (
        "<<<<<<< SEARCH\n"
        "    return a + b\n"
        "=======\n"
        "    return (a +\n"
        ">>>>>>> REPLACE"
    )
    new_content, error_kind, error_message = apply_and_verify(original, response_text)
    assert new_content is None
    assert error_kind == "syntax"
    assert bool(error_message)
