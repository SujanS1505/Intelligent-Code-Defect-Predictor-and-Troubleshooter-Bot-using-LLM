list = 10  # BUG: shadows built-in 'list'
print(list(['a','b']))  # TypeError
