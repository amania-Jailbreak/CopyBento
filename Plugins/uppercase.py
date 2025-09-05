# Sample plugin: convert text to uppercase on copy
NAME = "Uppercase Text"


def on_clipboard(data_type, value):
    if data_type == "text" and isinstance(value, str):
        return ("text", value.upper())
    # None -> unchanged
    return None
