from benchjoe.prompt import build_prompt


def test_prompt_contains_description():
    desc = "Heap buffer overflow in libpng when processing IHDR chunk"
    prompt = build_prompt(desc)
    assert desc in prompt


def test_prompt_mentions_poc_file():
    prompt = build_prompt("some vulnerability")
    assert "poc" in prompt.lower()


def test_prompt_mentions_repo():
    prompt = build_prompt("some vulnerability")
    assert "repo-vul.tar.gz" in prompt


def test_prompt_natural_language():
    prompt = build_prompt("some vulnerability")
    # Should not contain CyberGym's structured template markers
    assert "files_description" not in prompt
    assert "submit_instructions" not in prompt
    assert "##" not in prompt


def test_prompt_includes_error_output():
    prompt = build_prompt("heap overflow", error_output="ASAN: heap-buffer-overflow at 0x...")
    assert "heap-buffer-overflow" in prompt


def test_prompt_no_error_output_when_none():
    prompt = build_prompt("some vulnerability", error_output=None)
    assert "For reference" not in prompt
