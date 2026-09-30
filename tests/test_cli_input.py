import main


def test_normalize_input_strips_whitespace():
    assert main._normalize_input("   hello   ") == "hello"


def test_normalize_input_of_blank_line_is_empty_string():
    assert main._normalize_input("   ") == ""


def test_is_exit_command_case_insensitive():
    assert main._is_exit_command("exit")
    assert main._is_exit_command("EXIT")
    assert main._is_exit_command("Exit")


def test_is_exit_command_rejects_other_text():
    assert not main._is_exit_command("exit now")
    assert not main._is_exit_command("")
    assert not main._is_exit_command("hello")
