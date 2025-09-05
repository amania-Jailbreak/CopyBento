# Sample plugin: convert text to uppercase on copy
NAME = "Better Shot"


def on_clipboard(data_type, value):
    if data_type == "image":
        print("Better Shot Plugin Applied")
        return ("image [Edited Better Shot]", value)
