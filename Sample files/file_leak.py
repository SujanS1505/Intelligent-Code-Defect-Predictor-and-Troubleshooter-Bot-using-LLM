def read_file(path):
    f = open(path, 'r')
    content = f.read()
    # BUG: file not closed
    return content
